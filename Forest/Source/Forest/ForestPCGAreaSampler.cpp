#include "ForestPCGAreaSampler.h"

#include "Data/PCGPointData.h"
#include "Data/PCGSurfaceData.h"
#include "Elements/PCGSurfaceSampler.h"
#include "Helpers/PCGHelpers.h"
#include "Helpers/PCGSettingsHelpers.h"
#include "PCGContext.h"
#include "Math/RandomStream.h"

namespace ForestPCGAreaSampler
{
	struct FSpan { int32 Y, MinX, MaxX; };
	struct FIteration
	{
		const UPCGSurfaceData* Surface = nullptr;
		UPCGPointData* Output = nullptr;
		PCGSurfaceSampler::FSurfaceSamplerData Grid;
		TArray<FSpan> Spans;
	};
	struct FContext : FPCGContext
	{
		const UPCGSpatialData* Region = nullptr;
		const UPCGSpatialData* Bounds = nullptr;
		TArray<FIteration> Iterations;
	};

	// UE 5.8 PCGSurfaceSampler.cpp:116-158,239-256 enumerates/allocates a whole rectangle;
	// there is no exported sparse iterator. Store only covered row spans, never a cell array.
	// Invert the entire jitter interval, not just tile origin bounds (boundary cells can jitter in).
	static void BuildSpans(const PCGSurfaceSampler::FSurfaceSamplerData& Grid,
		const TArray<FBox>& Tiles, TArray<FSpan>& Spans)
	{
		const FVector A = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMin(FVector::ZeroVector);
		const FVector B = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMax(FVector::ZeroVector);
		for (const FBox& Tile : Tiles)
		{
			const double MinX = FMath::Max<double>(Grid.CellMinX, FMath::CeilToDouble((Tile.Min.X - B.X) / Grid.CellSize.X));
			const double MaxX = FMath::Min<double>(Grid.CellMaxX, FMath::FloorToDouble((Tile.Max.X - A.X) / Grid.CellSize.X));
			const double MinY = FMath::Max<double>(Grid.CellMinY, FMath::CeilToDouble((Tile.Min.Y - B.Y) / Grid.CellSize.Y));
			const double MaxY = FMath::Min<double>(Grid.CellMaxY, FMath::FloorToDouble((Tile.Max.Y - A.Y) / Grid.CellSize.Y));
			if (MinX > MaxX || MinY > MaxY) { continue; }
			for (int64 Y = static_cast<int64>(MinY); Y <= static_cast<int64>(MaxY); ++Y)
			{
				Spans.Add({static_cast<int32>(Y), static_cast<int32>(MinX), static_cast<int32>(MaxX)});
			}
		}
		Spans.Sort([](const FSpan& ASpan, const FSpan& BSpan)
		{
			return ASpan.Y == BSpan.Y ? ASpan.MinX < BSpan.MinX : ASpan.Y < BSpan.Y;
		});
		int32 Count = 0;
		for (int32 I = 0; I < Spans.Num(); ++I)
		{
			const FSpan Span = Spans[I];
			if (Count && Spans[Count - 1].Y == Span.Y && int64(Span.MinX) <= int64(Spans[Count - 1].MaxX) + 1)
			{
				Spans[Count - 1].MaxX = FMath::Max(Spans[Count - 1].MaxX, Span.MaxX);
			}
			else { Spans[Count++] = Span; }
		}
		Spans.SetNum(Count, EAllowShrinking::No);
	}

	static void Sample(FContext* Context, FIteration& Iteration)
	{
		const auto& Grid = Iteration.Grid;
		const auto& Params = Grid.Params;
		TArray<FPCGPoint>& Points = Iteration.Output->GetMutablePoints();
		// UE 5.8 PCGSurfaceSampler.cpp:269-351 is the reference for draw order, projection,
		// bounding density and emitted properties. Its exported helper cannot accept sparse cells.
		for (const FSpan& Span : Iteration.Spans)
		{
			for (int64 X = Span.MinX; X <= Span.MaxX; ++X)
			{
				FRandomStream Random(PCGHelpers::ComputeSeed(Grid.Seed, static_cast<int32>(X), Span.Y));
				const float Chance = Random.FRand();
				if (Chance >= Grid.Ratio) { continue; }
				const float RandX = Random.FRand();
				const float RandY = Random.FRand();
				FVector Location(X * Grid.CellSize.X + Grid.InnerCellOffset.X + RandX * Grid.InnerCellSize.X,
					Span.Y * Grid.CellSize.Y + Grid.InnerCellOffset.Y + RandY * Grid.InnerCellSize.Y, Grid.PreProjectionDisplacement);
				if (Grid.bNeedsLocalTransformation) { Location = Grid.PreProjectionTransform.TransformPosition(Location); }
				FPCGPoint Point;
				if (!Iteration.Surface->ProjectPoint(FTransform(Location), FBox(-Params.PointExtents, Params.PointExtents),
					{}, Point, Iteration.Output->Metadata)) { continue; }
				Point.SetExtents(Params.PointExtents);
				Point.Steepness = Params.PointSteepness;
				FPCGPoint RegionSample;
				if (!Context->Region->SamplePoint(Point.Transform, FBox(FVector::ZeroVector, FVector::ZeroVector), RegionSample, nullptr)
					|| RegionSample.Density <= 0) { continue; }
				Point.Density = 1.0f;
				if (Context->Bounds)
				{
					FPCGPoint BoundSample;
					const bool bInside = Context->Bounds->SamplePoint(Point.Transform, Point.GetLocalBounds(), BoundSample, nullptr);
#if WITH_EDITOR
					if (!bInside && !Params.bKeepZeroDensityPoints) { continue; }
#else
					if (!bInside) { continue; }
#endif
					Point.Density *= BoundSample.Density;
				}
				if (Params.bApplyDensityToPoints) { Point.Density *= (Grid.Ratio - Chance) / Grid.Ratio; }
				// Stock queries with projected local centre, but emits its default centred bounds.
				Point.SetLocalBounds(FBox(-Params.PointExtents, Params.PointExtents));
				Point.Seed = Random.GetCurrentSeed();
				Points.Add(Point); // Only accepted points allocate storage. Metadata keys may differ from stock.
			}
		}
	}

	class FElement : public IPCGElement
	{
	public:
		virtual bool SupportsBasePointDataInputs(FPCGContext*) const override { return true; }
		virtual bool ShouldComputeFullOutputDataCrc(FPCGContext*) const override { return true; }
		virtual void GetDependenciesCrc(const FPCGGetDependenciesCrcParams& Params, FPCGCrc& Crc) const override
		{
			IPCGElement::GetDependenciesCrc(Params, Crc);
			const auto* Settings = CastChecked<UForestPCGAreaSamplerSettings>(Params.Settings);
			bool bUnbounded;
			PCGSettingsHelpers::GetOverrideValue(*Params.InputData, Settings,
				GET_MEMBER_NAME_CHECKED(UForestPCGAreaSamplerSettings, bUnbounded), Settings->bUnbounded, bUnbounded);
			if (!bUnbounded && Params.InputData->GetInputsByPin(PCGSurfaceSamplerConstants::BoundingShapeLabel).IsEmpty() && Params.ExecutionSource)
			{
				if (const UPCGData* Self = Params.ExecutionSource->GetExecutionState().GetSelfData())
				{ Crc.Combine(Self->GetOrComputeCrc(false)); }
			}
		}
	protected:
		virtual FPCGContext* CreateContext() override { return new FContext; }
		virtual bool PrepareDataInternal(FPCGContext* InContext) const override
		{
			auto* Context = static_cast<FContext*>(InContext);
			const auto* Settings = Context->GetInputSettings<UForestPCGAreaSamplerSettings>();
			const auto Regions = Context->InputData.GetInputsByPin(RegionLabel);
			if (Regions.Num() != 1 || !(Context->Region = Cast<UPCGSpatialData>(Regions[0].Data)))
			{
				PCGE_LOG(Error, GraphAndLog, NSLOCTEXT("Forest", "MissingRegion", "Supply one exact spatial Region and conservative Region Tiles."));
				return true;
			}
			TArray<FBox> Tiles;
			for (const auto& Tagged : Context->InputData.GetInputsByPin(TilesLabel))
			{
				if (const auto* Data = Cast<UPCGBasePointData>(Tagged.Data))
				{
					const auto Transforms = Data->GetConstTransformValueRange();
					const auto Min = Data->GetConstBoundsMinValueRange();
					const auto Max = Data->GetConstBoundsMaxValueRange();
					for (int32 I = 0; I < Data->GetNumPoints(); ++I)
					{
						const FBox Box = FBox(Min[I], Max[I]).TransformBy(Transforms[I]);
						if (Box.IsValid && !Box.Min.ContainsNaN() && !Box.Max.ContainsNaN()) { Tiles.Add(Box); }
					}
				}
			}
			if (Tiles.IsEmpty()) { return true; }
			FBox Bounds(ForceInit);
			if (!Settings->bUnbounded)
			{
				bool bUnionCreated;
				Context->Bounds = PCGSettingsHelpers::ComputeBoundingShape(Context, PCGSurfaceSamplerConstants::BoundingShapeLabel, bUnionCreated);
				if (bUnionCreated) { Context->TrackObject(Context->Bounds); }
				if (Context->Bounds) { Bounds = Context->Bounds->GetBounds(); }
				if (!Bounds.IsValid) { return true; }
			}
			for (const auto& Tagged : Context->InputData.GetInputsByPin(PCGSurfaceSamplerConstants::SurfaceLabel))
			{
				const auto* Surface = Cast<UPCGSurfaceData>(Tagged.Data);
				if (!Surface) { continue; }
				// Same domain as stock PrepareDataInternal (PCGSurfaceSampler.cpp:596-627).
				// Region NEVER shrinks this domain, otherwise the legacy Ratio and boundary cells change.
				FBox Domain = Surface->GetLocalBounds();
				if (Domain.IsValid) { Domain = PCGHelpers::OverlapBounds(Domain.TransformBy(Surface->GetTransform()), Bounds); }
				else if (Surface->IsBounded())
				{
					Domain = Surface->GetBounds();
					if (Bounds.IsValid) { Domain = PCGHelpers::OverlapBounds(Domain, Bounds); }
				}
				else { Domain = Bounds; }
				FIteration Iteration;
				Iteration.Surface = Surface;
				auto& Grid = Iteration.Grid;
				Grid.Params.bUseLegacyGridCreationMethod = Settings->bUseLegacyGridCreationMethod;
				Grid.Params.PointsPerSquaredMeter = Settings->PointsPerSquaredMeter;
				Grid.Params.PointExtents = Settings->PointExtents;
				Grid.Params.Looseness = Settings->Looseness;
				Grid.Params.PointSteepness = Settings->PointSteepness;
				Grid.Params.bApplyDensityToPoints = Settings->bApplyDensityToPoints;
#if WITH_EDITOR
				Grid.Params.bKeepZeroDensityPoints = Settings->bKeepZeroDensityPoints;
#endif
				// Exported initializer retains stock grid, Ratio, seed, transforms and validation.
				if (!Grid.Initialize(Context, Domain, Surface->GetTransform())) { continue; }
				BuildSpans(Grid, Tiles, Iteration.Spans);
				Iteration.Output = FPCGContext::NewObject_AnyThread<UPCGPointData>(Context);
				Iteration.Output->InitializeFromData(Surface);
				FPCGTaggedData& Output = Context->OutputData.TaggedData.Add_GetRef(Tagged);
				Output.Pin = PCGPinConstants::DefaultOutputLabel;
				Output.Data = Iteration.Output;
				FBox QueryBounds = Grid.bNeedsLocalTransformation ? Domain.TransformBy(Grid.PreProjectionTransform) : Domain;
				Context->DynamicDependencies.Append(Surface->PrepareForSpatialQuery(Context, QueryBounds));
				Context->Iterations.Add(MoveTemp(Iteration));
			}
			Context->bIsPaused = !Context->DynamicDependencies.IsEmpty();
			return true;
		}
		virtual bool ExecuteInternal(FPCGContext* InContext) const override
		{
			auto* Context = static_cast<FContext*>(InContext);
			if (Context->bIsPaused) { return false; }
			for (FIteration& Iteration : Context->Iterations) { Sample(Context, Iteration); }
			return true;
		}
	};
}

UForestPCGAreaSamplerSettings::UForestPCGAreaSamplerSettings()
{
	if (PCGHelpers::IsNewObjectAndNotDefault(this)) { PointSteepness = 1.0f; }
}

TArray<FPCGPinProperties> UForestPCGAreaSamplerSettings::InputPinProperties() const
{
	TArray<FPCGPinProperties> Pins;
	Pins.Emplace(PCGSurfaceSamplerConstants::SurfaceLabel, EPCGDataType::Surface);
	Pins.Last().SetRequiredPin();
	Pins.Emplace(PCGSurfaceSamplerConstants::BoundingShapeLabel, EPCGDataType::Spatial, false, false);
	Pins.Emplace(ForestPCGAreaSampler::TilesLabel, EPCGDataType::Point);
	Pins.Last().SetRequiredPin();
	Pins.Emplace(ForestPCGAreaSampler::RegionLabel, EPCGDataType::Spatial, false, false);
	Pins.Last().SetRequiredPin();
	return Pins;
}

TArray<FPCGPinProperties> UForestPCGAreaSamplerSettings::OutputPinProperties() const
{
	return {FPCGPinProperties(PCGPinConstants::DefaultOutputLabel, EPCGDataType::Point)};
}

FPCGElementPtr UForestPCGAreaSamplerSettings::CreateElement() const
{
	return MakeShared<ForestPCGAreaSampler::FElement>();
}
