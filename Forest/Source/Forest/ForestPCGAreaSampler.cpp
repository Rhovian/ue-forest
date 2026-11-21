#include "ForestPCGAreaSampler.h"

#include "Data/PCGBasePointData.h"
#include "Data/PCGSurfaceData.h"
#include "Elements/PCGSurfaceSampler.h"
#include "Helpers/PCGHelpers.h"
#include "Helpers/PCGSettingsHelpers.h"
#include "PCGContext.h"
#include "Math/RandomStream.h"

namespace ForestPCGAreaSampler
{
	struct FSpan
	{
		int32 Y, MinX, MaxX;
	};
	struct FIteration
	{
		const UPCGSurfaceData* Surface = nullptr;
		UPCGBasePointData* Output = nullptr;
		PCGSurfaceSampler::FSurfaceSamplerData Grid;
		TArray<FSpan> Spans;
	};
	struct FContext : FPCGContext
	{
		const UPCGSpatialData* Region = nullptr;
		TObjectPtr<const UPCGSpatialData> Bounds = nullptr;
		TArray<FIteration> Iterations;
		virtual void AddExtraStructReferencedObjects(FReferenceCollector& Collector) override
		{
			// UE 5.8 PCGContext.h:245-250 exposes this GC hook; TrackObject belongs only
			// to TPCGTimeSlicedContext (Elements/PCGTimeSlicedElementBase.h:107,169-172).
			Collector.AddReferencedObject(Bounds);
		}
	};

	// UE 5.8 PCGSurfaceSampler.cpp:116-158,239-256 enumerates/allocates a whole rectangle;
	// there is no exported sparse iterator. Store only covered row spans, never a cell array.
	// Invert the entire jitter interval, not just tile origin bounds (boundary cells can jitter in).
	static void BuildSpans(const PCGSurfaceSampler::FSurfaceSamplerData& Grid,
		const TArray<FBox>& Tiles, TArray<FSpan>& Spans)
	{
		const FVector A = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMin(FVector::ZeroVector);
		const FVector B = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMax(FVector::ZeroVector);
		// FSurfaceSamplerData::Initialize clips nominal origins, not their jitter footprints (PCGSurfaceSampler.cpp).
		// Pad traversal only: changing its CellCount would also change the legacy Ratio. Bound int32 span indices.
		for (const FBox& Tile : Tiles)
		{
			const double MinX = FMath::Max3<double>(MIN_int32, Grid.CellMinX - FMath::CeilToDouble(B.X / Grid.CellSize.X),
				FMath::CeilToDouble((Tile.Min.X - B.X) / Grid.CellSize.X));
			const double MaxX = FMath::Min3<double>(MAX_int32, Grid.CellMaxX - FMath::FloorToDouble(A.X / Grid.CellSize.X),
				FMath::FloorToDouble((Tile.Max.X - A.X) / Grid.CellSize.X));
			const double MinY = FMath::Max3<double>(MIN_int32, Grid.CellMinY - FMath::CeilToDouble(B.Y / Grid.CellSize.Y),
				FMath::CeilToDouble((Tile.Min.Y - B.Y) / Grid.CellSize.Y));
			const double MaxY = FMath::Min3<double>(MAX_int32, Grid.CellMaxY - FMath::FloorToDouble(A.Y / Grid.CellSize.Y),
				FMath::FloorToDouble((Tile.Max.Y - A.Y) / Grid.CellSize.Y));
			if (MinX > MaxX || MinY > MaxY)
			{
				continue;
			}
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
			else
			{
				Spans[Count++] = Span;
			}
		}
		Spans.SetNum(Count, EAllowShrinking::No);
	}

	static void Sample(FContext* Context, FIteration& Iteration)
	{
		const auto& Grid = Iteration.Grid;
		const auto& Params = Grid.Params;
		UPCGBasePointData* Output = Iteration.Output;
		// UE 5.8 PCGSurfaceSampler.cpp:269-351 is the reference for draw order, projection,
		// bounding density and emitted properties. Its exported helper cannot accept sparse cells.
		for (const FSpan& Span : Iteration.Spans)
		{
			for (int64 X = Span.MinX; X <= Span.MaxX; ++X)
			{
				FRandomStream Random(PCGHelpers::ComputeSeed(Grid.Seed, static_cast<int32>(X), Span.Y));
				const float Chance = Random.FRand();
				if (Chance >= Grid.Ratio)
				{
					continue;
				}
				const float RandX = Random.FRand();
				const float RandY = Random.FRand();
				FVector Location(X * Grid.CellSize.X + Grid.InnerCellOffset.X + RandX * Grid.InnerCellSize.X,
					Span.Y * Grid.CellSize.Y + Grid.InnerCellOffset.Y + RandY * Grid.InnerCellSize.Y, Grid.PreProjectionDisplacement);
				if (Grid.bNeedsLocalTransformation)
				{
					Location = Grid.PreProjectionTransform.TransformPosition(Location);
				}
				FPCGPoint Point;
				if (!Iteration.Surface->ProjectPoint(FTransform(Location), FBox(-Params.PointExtents, Params.PointExtents),
					{}, Point, Iteration.Output->Metadata))
				{
					continue;
				}
				Point.SetExtents(Params.PointExtents);
				Point.Steepness = Params.PointSteepness;
				FPCGPoint RegionSample;
				if (!Context->Region->SamplePoint(Point.Transform, FBox(FVector::ZeroVector, FVector::ZeroVector), RegionSample, nullptr)
					|| RegionSample.Density <= 0)
				{
					continue;
				}
				Point.Density = 1.0f;
				if (Context->Bounds)
				{
					FPCGPoint BoundSample;
					const bool bInside = Context->Bounds->SamplePoint(Point.Transform, Point.GetLocalBounds(), BoundSample, nullptr);
#if WITH_EDITOR
					if (!bInside && !Params.bKeepZeroDensityPoints)
					{
						continue;
					}
#else
					if (!bInside)
					{
						continue;
					}
#endif
					Point.Density *= BoundSample.Density;
				}
				if (Params.bApplyDensityToPoints)
				{
					Point.Density *= (Grid.Ratio - Chance) / Grid.Ratio;
				}
				// PCGPointArray.h:79-98 uses TArray growth; no separate batching/growth mechanism.
				// Append only accepted points, using stock's selected container and dynamic properties.
				const int32 Index = Output->GetNumPoints();
				Output->SetNumPoints(Index + 1, false);
				Output->GetTransformValueRange()[Index] = Point.Transform;
				Output->GetDensityValueRange()[Index] = Point.Density;
				Output->GetSeedValueRange()[Index] = Random.GetCurrentSeed();
				Output->GetMetadataEntryValueRange()[Index] = Point.MetadataEntry;
				Output->GetColorValueRange()[Index] = Point.Color;
			}
		}
		// Stock emits centred bounds and shared constants (PCGSurfaceSampler.cpp:239-256).
		// Base setters retain singleton storage on arrays, and fill all points on legacy data.
		Output->SetBoundsMin(-Params.PointExtents);
		Output->SetBoundsMax(Params.PointExtents);
		Output->SetSteepness(Params.PointSteepness);
	}

	class FElement : public IPCGElement
	{
	public:
		virtual bool SupportsBasePointDataInputs(FPCGContext*) const override
		{
			return true;
		}
		virtual bool ShouldComputeFullOutputDataCrc(FPCGContext*) const override
		{
			return true;
		}
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
				{
					Crc.Combine(Self->GetOrComputeCrc(false));
				}
			}
		}
	protected:
		virtual FPCGContext* CreateContext() override
		{
			return new FContext;
		}
		virtual bool PrepareDataInternal(FPCGContext* InContext) const override
		{
			auto* Context = static_cast<FContext*>(InContext);
			const auto* Settings = Context->GetInputSettings<UForestPCGAreaSamplerSettings>();
			// Emit one tagged empty datum per surface before any no-operation/invalid-region path.
			// Stock does this for execution and iteration NoOperation (PCGSurfaceSampler.cpp:698-718).
			for (const auto& Tagged : Context->InputData.GetInputsByPin(PCGSurfaceSamplerConstants::SurfaceLabel))
			{
				if (const auto* Surface = Cast<UPCGSurfaceData>(Tagged.Data))
				{
					FIteration& Iteration = Context->Iterations.Emplace_GetRef();
					Iteration.Surface = Surface;
					Iteration.Output = FPCGContext::NewPointData_AnyThread(Context);
					Iteration.Output->InitializeFromData(Surface);
					FPCGTaggedData& Output = Context->OutputData.TaggedData.Add_GetRef(Tagged);
					Output.Pin = PCGPinConstants::DefaultOutputLabel;
					Output.Data = Iteration.Output;
				}
			}
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
						if (Box.IsValid && !Box.Min.ContainsNaN() && !Box.Max.ContainsNaN())
						{
							Tiles.Add(Box);
						}
					}
				}
			}
			if (Tiles.IsEmpty())
			{
				return true;
			}
			FBox Bounds(ForceInit);
			if (!Settings->bUnbounded)
			{
				bool bUnionCreated;
				Context->Bounds = PCGSettingsHelpers::ComputeBoundingShape(Context, PCGSurfaceSamplerConstants::BoundingShapeLabel, bUnionCreated);
				if (Context->Bounds)
				{
					Bounds = Context->Bounds->GetBounds();
				}
				if (!Bounds.IsValid)
				{
					return true;
				}
			}
			for (int32 Index = 0; Index < Context->Iterations.Num(); ++Index)
			{
				FIteration& Iteration = Context->Iterations[Index];
				const auto* Surface = Iteration.Surface;
				// Same domain as stock PrepareDataInternal (PCGSurfaceSampler.cpp:596-627).
				// Region NEVER shrinks this domain, otherwise the legacy Ratio and boundary cells change.
				FBox Domain = Surface->GetLocalBounds();
				if (Domain.IsValid)
				{
					Domain = PCGHelpers::OverlapBounds(Domain.TransformBy(Surface->GetTransform()), Bounds);
				}
				else if (Surface->IsBounded())
				{
					Domain = Surface->GetBounds();
					if (Bounds.IsValid)
					{
						Domain = PCGHelpers::OverlapBounds(Domain, Bounds);
					}
				}
				else
				{
					Domain = Bounds;
				}
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
				if (!Grid.Initialize(Context, Domain, Surface->GetTransform()))
				{
					// Stock iteration NoOperation replaces its initialized output with fresh point data.
					Iteration.Output = FPCGContext::NewPointData_AnyThread(Context);
					Context->OutputData.TaggedData[Index].Data = Iteration.Output;
					continue;
				}
				BuildSpans(Grid, Tiles, Iteration.Spans);
				if (Iteration.Spans.IsEmpty())
				{
					continue;
				}
				// Prime only the possible queries of the visited cells. Tile bounds alone are not
				// enough: boundary cells can jitter beyond the cover. Stock's prepare API takes one box.
				FBox QueryBounds(ForceInit);
				const FVector A = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMin(FVector::ZeroVector);
				const FVector B = Grid.InnerCellOffset + Grid.InnerCellSize.ComponentMax(FVector::ZeroVector);
				for (const FSpan& Span : Iteration.Spans)
				{
					QueryBounds += FVector(Span.MinX * Grid.CellSize.X + A.X, Span.Y * Grid.CellSize.Y + A.Y, Domain.Min.Z);
					QueryBounds += FVector(Span.MaxX * Grid.CellSize.X + B.X, Span.Y * Grid.CellSize.Y + B.Y, Domain.Max.Z);
				}
				if (Grid.bNeedsLocalTransformation)
				{
					QueryBounds = QueryBounds.TransformBy(Grid.PreProjectionTransform);
				}
				QueryBounds = QueryBounds.ExpandBy(Grid.Params.PointExtents.GetAbs());
				Context->DynamicDependencies.Append(Surface->PrepareForSpatialQuery(Context, QueryBounds));
			}
			Context->bIsPaused = !Context->DynamicDependencies.IsEmpty();
			return true;
		}
		virtual bool ExecuteInternal(FPCGContext* InContext) const override
		{
			auto* Context = static_cast<FContext*>(InContext);
			if (Context->bIsPaused)
			{
				return false;
			}
			for (FIteration& Iteration : Context->Iterations)
			{
				if (!Iteration.Spans.IsEmpty())
				{
					Sample(Context, Iteration);
				}
			}
			return true;
		}
	};
}

UForestPCGAreaSamplerSettings::UForestPCGAreaSamplerSettings()
{
	if (PCGHelpers::IsNewObjectAndNotDefault(this))
	{
		PointSteepness = 1.0f;
	}
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
