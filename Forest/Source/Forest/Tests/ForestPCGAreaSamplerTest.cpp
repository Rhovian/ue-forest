#include "../ForestPCGAreaSampler.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ForestPCGAreaSamplerTestData.h"
#include "Data/PCGPointData.h"
#include "Data/PCGPointArrayData.h"
#include "Data/PCGVolumeData.h"
#include "Elements/PCGSurfaceSampler.h"
#include "Misc/AutomationTest.h"
#include "PCGContext.h"

static TUniquePtr<FPCGContext> RunSampler(UPCGSettings* Settings, const UPCGSpatialData* InSurface,
	const UPCGSpatialData* InBounds, const UPCGSpatialData* Region, const UPCGPointData* Tiles)
{
	FPCGDataCollection Inputs;
	auto Add = [&](const UPCGData* Data, FName Pin)
	{
		if (!Data)
		{
			return;
		}
		FPCGTaggedData& Tagged = Inputs.TaggedData.Emplace_GetRef();
		Tagged.Data = Data;
		Tagged.Pin = Pin;
		Tagged.Tags.Add(TEXT("GEN:Identity"));
	};
	Add(Settings, TEXT("Settings"));
	Add(InSurface, PCGSurfaceSamplerConstants::SurfaceLabel);
	Add(InBounds, PCGSurfaceSamplerConstants::BoundingShapeLabel);
	Add(Region, ForestPCGAreaSampler::RegionLabel);
	Add(Tiles, ForestPCGAreaSampler::TilesLabel);
	FPCGElementPtr Element = Settings->GetElement();
	TUniquePtr<FPCGContext> Context(Element->Initialize(FPCGInitializeElementParams(&Inputs, {}, nullptr)));
	Context->InitializeSettings();
	Context->AsyncState.NumAvailableTasks = 1;
	while (!Element->Execute(Context.Get()))
	{
	}
	return Context;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForestAreaSamplerIdentityTest, "Forest.PCG.AreaSampler.Identity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForestAreaSamplerIdentityTest::RunTest(const FString& Parameters)
{
	const FPCGAttributeIdentifier SurfaceKind(TEXT("SurfaceKind"), PCGMetadataDomainID::Data);
	// No existing project sampler test: UniqueGeneratedLocations covers only output collection.
	// Each mode needs full and cropped comparisons: cropping changes Ratio only in legacy mode.
	for (const bool bLegacy : {false, true})
	{
		UForestPCGAreaSamplerTestSurface* Surface = NewObject<UForestPCGAreaSamplerTestSurface>();
		Surface->Metadata->CreateAttribute<double>(TEXT("Elevation"), -1, false, false);
		Surface->Metadata->CreateAttribute<int32>(SurfaceKind, 247, false, false);
		UForestPCGAreaSamplerTestBounds* Bounds = NewObject<UForestPCGAreaSamplerTestBounds>();
		Bounds->Initialize(Surface->Bounds);
		UPCGSurfaceSamplerSettings* StockSettings = NewObject<UPCGSurfaceSamplerSettings>();
		StockSettings->Seed = 7281;
		StockSettings->bUseLegacyGridCreationMethod = bLegacy;
		StockSettings->PointsPerSquaredMeter = 0.047f;
		StockSettings->PointExtents = FVector(61, 43, 27);
		StockSettings->Looseness = 0.81f;
		StockSettings->PointSteepness = 0.73f;
		StockSettings->bApplyDensityToPoints = true;

		auto Stock = RunSampler(StockSettings, Surface, Bounds, nullptr, nullptr);
		UTEST_EQUAL("One stock surface output", Stock->OutputData.TaggedData.Num(), 1);
		const auto* StockPoints = Cast<UPCGBasePointData>(Stock->OutputData.TaggedData[0].Data);
		UTEST_NOT_NULL("Stock points", StockPoints);
		// UE 5.8 PCGSpatialData.cpp:85 / PCGBasePointData.cpp:532: surface defaults to Data,
		// points to Elements. InitializeTargetMetadata preserves domains without remapping.
		const auto* StockInherited = StockPoints->Metadata->GetConstTypedAttribute<int32>(SurfaceKind);
		UTEST_NOT_NULL("Stock inherited surface attribute in Data domain", StockInherited);
		UTEST_EQUAL("Stock inherited default value", StockInherited->GetValueFromItemKey(PCGInvalidEntryKey), 247);
		UTEST_NULL("Stock surface attribute is not point metadata", StockPoints->Metadata->GetConstTypedAttribute<int32>(TEXT("SurfaceKind")));
		TestTrue(TEXT("Non-empty reference"), StockPoints->GetNumPoints() > 10);
		const int32 FullProjections = Surface->Projections;
		const FConstPCGPointValueRanges StockRanges(StockPoints);

		UForestPCGAreaSamplerSettings* AreaSettings = NewObject<UForestPCGAreaSamplerSettings>();
		AreaSettings->Seed = StockSettings->Seed;
		AreaSettings->bUseLegacyGridCreationMethod = bLegacy;
		AreaSettings->PointsPerSquaredMeter = StockSettings->PointsPerSquaredMeter;
		AreaSettings->PointExtents = StockSettings->PointExtents;
		AreaSettings->Looseness = StockSettings->Looseness;
		AreaSettings->PointSteepness = StockSettings->PointSteepness;
		AreaSettings->bApplyDensityToPoints = StockSettings->bApplyDensityToPoints;
		PCGSurfaceSampler::FSurfaceSamplerData FixtureGrid;
		FixtureGrid.Params.bUseLegacyGridCreationMethod = bLegacy;
		FixtureGrid.Params.PointsPerSquaredMeter = StockSettings->PointsPerSquaredMeter;
		FixtureGrid.Params.PointExtents = StockSettings->PointExtents;
		FixtureGrid.Params.Looseness = StockSettings->Looseness;
		UTEST_TRUE("Fixture grid initializes", FixtureGrid.Initialize(nullptr, Surface->Bounds));
		for (const bool bCrop : {false, true})
		{
			// A tight crop around a known stock sample also catches omitting cells whose origins
			// are outside the crop but whose jittered samples enter it. Non-empty by construction.
			FVector Centre = StockRanges.GetPoint(0).Transform.GetLocation();
			for (int32 I = 1; I < StockPoints->GetNumPoints(); ++I)
			{
				const FVector P = StockRanges.GetPoint(I).Transform.GetLocation();
				if (P.X < Centre.X)
				{
					Centre = P;
				}
			}
			const FBox RegionBox = bCrop
				? FBox(Centre - FVector(1, 1, 1000), Centre + FVector(1, 1, 1000)) : Surface->Bounds;
			auto* Region = NewObject<UForestPCGAreaSamplerTestBounds>();
			Region->InsideDensity = 0.25f;
			Region->bCutCorner = false;
			Region->Initialize(RegionBox);
			UPCGPointData* Tiles = NewObject<UPCGPointData>();
			// Distinct MinX on one row, left then right. UE 5.8 Algo/IntroSort.h:64-86
			// swaps two equal-Y elements: a Y-only comparator then drops the left sample.
			// Shift by one CELL (not arbitrary world units) so both tiny tiles hit jitter footprints.
			for (const double Offset : {0.0, bCrop ? FixtureGrid.CellSize.X : RegionBox.GetExtent().X})
			{
				FBox Box = RegionBox;
				if (bCrop)
				{
					Box = Box.ShiftBy(FVector(Offset, 0, 0));
				}
				else
				{
					Box.Min.X += Offset;
				}
				FPCGPoint& Tile = Tiles->GetMutablePoints().Emplace_GetRef();
				Tile.SetLocalBounds(Box);
			}
			Surface->Projections = 0;
			auto Area = RunSampler(AreaSettings, Surface, Bounds, Region, Tiles);
			UTEST_EQUAL("One area surface output", Area->OutputData.TaggedData.Num(), 1);
			const auto* Actual = Cast<UPCGBasePointData>(Area->OutputData.TaggedData[0].Data);
			UTEST_NOT_NULL("Area points", Actual);
			TestTrue(TEXT("Container matches stock without conversion"), Actual->GetClass() == StockPoints->GetClass());
			if (Cast<UPCGPointArrayData>(Actual))
			{
				TestFalse(TEXT("Bounds and steepness remain shared"), EnumHasAnyFlags(Actual->GetAllocatedProperties(),
					EPCGPointNativeProperties::BoundsMin | EPCGPointNativeProperties::BoundsMax | EPCGPointNativeProperties::Steepness));
			}
			const FConstPCGPointValueRanges ActualRanges(Actual);
			TestTrue(TEXT("Tags retained"), Area->OutputData.TaggedData[0].Tags.Contains(TEXT("GEN:Identity")));
			TestEqual(TEXT("Output pin"), Area->OutputData.TaggedData[0].Pin, PCGPinConstants::DefaultOutputLabel);
			TArray<FPCGPoint> Expected;
			for (int32 I = 0; I < StockPoints->GetNumPoints(); ++I)
			{
				const FPCGPoint Point = StockRanges.GetPoint(I);
				FPCGPoint Sample;
				if (Region->SamplePoint(Point.Transform, FBox(FVector::ZeroVector, FVector::ZeroVector), Sample, nullptr)
					&& Sample.Density > 0)
				{
					Expected.Add(Point);
				}
			}
			TestTrue(TEXT("Crop is a strict non-empty subset"), !bCrop || (Expected.Num() > 0 && Expected.Num() < StockPoints->GetNumPoints()));
			TestTrue(TEXT("Full region covers every stock point"), bCrop || Expected.Num() == StockPoints->GetNumPoints());
			UTEST_EQUAL("Exact subset count", Actual->GetNumPoints(), Expected.Num());
			const auto* StockAttribute = StockPoints->Metadata->GetConstTypedAttribute<double>(TEXT("Elevation"));
			const auto* AreaAttribute = Actual->Metadata->GetConstTypedAttribute<double>(TEXT("Elevation"));
			UTEST_NOT_NULL("Stock attribute", StockAttribute);
			UTEST_NOT_NULL("Area attribute", AreaAttribute);
			const auto* Inherited = Actual->Metadata->GetConstTypedAttribute<int32>(SurfaceKind);
			UTEST_NOT_NULL("Inherited surface attribute in Data domain", Inherited);
			TestEqual(TEXT("Inherited default value matches stock"), Inherited->GetValueFromItemKey(PCGInvalidEntryKey), StockInherited->GetValueFromItemKey(PCGInvalidEntryKey));
			for (int32 I = 0; I < Expected.Num(); ++I)
			{
				const FPCGPoint A = ActualRanges.GetPoint(I);
				const FPCGPoint& E = Expected[I];
				TestTrue(TEXT("Exact location and order"), A.Transform.GetLocation() == E.Transform.GetLocation());
				TestTrue(TEXT("Exact rotation/scale"), A.Transform.GetRotation() == E.Transform.GetRotation() && A.Transform.GetScale3D() == E.Transform.GetScale3D());
				TestEqual(TEXT("Seed"), A.Seed, E.Seed);
				TestEqual(TEXT("Density"), A.Density, E.Density);
				TestTrue(TEXT("Extents"), A.BoundsMin == E.BoundsMin && A.BoundsMax == E.BoundsMax);
				TestEqual(TEXT("Steepness"), A.Steepness, E.Steepness);
				TestTrue(TEXT("Color"), A.Color == E.Color);
				TestEqual(TEXT("Projected metadata value"), AreaAttribute->GetValueFromItemKey(A.MetadataEntry), StockAttribute->GetValueFromItemKey(E.MetadataEntry));
			}
			TestTrue(TEXT("Crop avoids outside-cell projections"), !bCrop || Surface->Projections < FullProjections / 3);
			TestFalse(TEXT("Prepare bounds cover every attempted query"), Surface->bOutsidePrepared);
			TestTrue(TEXT("Crop narrows preparation"), !bCrop || Surface->PreparedBounds.GetSize().X * Surface->PreparedBounds.GetSize().Y
				< Surface->Bounds.GetSize().X * Surface->Bounds.GetSize().Y / 3);
		}
	}
	// Partition seam identity needs real point-data bounds: the soft mask above ignores query extents.
	{
		auto* Surface = NewObject<UForestPCGAreaSamplerTestSurface>();
		Surface->Bounds = FBox(FVector(-400, -400, -100), FVector(400, 400, 600));
		auto* Region = NewObject<UPCGVolumeData>();
		Region->Initialize(Surface->Bounds.ExpandBy(100));
		auto* Tiles = NewObject<UPCGPointData>();
		Tiles->GetMutablePoints().Emplace_GetRef().SetLocalBounds(Surface->Bounds);
		auto* Settings = NewObject<UForestPCGAreaSamplerSettings>();
		Settings->PointsPerSquaredMeter = 1.0f; // 100 cm lattice, including centres exactly on Y = 0.
		Settings->bApplyDensityToPoints = false;
		auto MakeBounds = [](const FBox& Box)
		{
			auto* Data = NewObject<UPCGPointData>();
			FPCGPoint& Point = Data->GetMutablePoints().Emplace_GetRef();
			Point.SetLocalBounds(Box);
			Point.Steepness = 1.0f;
			return Data;
		};
		auto Whole = RunSampler(Settings, Surface, MakeBounds(Surface->Bounds), Region, Tiles);
		const auto* WholePoints = CastChecked<UPCGBasePointData>(Whole->OutputData.TaggedData[0].Data);
		TMap<FVector, int32> RemainingSeeds;
		for (int32 I = 0; I < WholePoints->GetNumPoints(); ++I)
		{
			const FPCGPoint Point = FConstPCGPointValueRanges(WholePoints).GetPoint(I);
			RemainingSeeds.Add(Point.Transform.GetLocation(), Point.Seed);
		}
		UTEST_TRUE("Fixture exercises an exact seam centre", RemainingSeeds.Contains(FVector(0, 0, 30)));
		for (const bool bUpper : {false, true})
		{
			FBox Cell = Surface->Bounds;
			(bUpper ? Cell.Min.Y : Cell.Max.Y) = 0;
			auto Part = RunSampler(Settings, Surface, MakeBounds(Cell), Region, Tiles);
			const auto* Points = CastChecked<UPCGBasePointData>(Part->OutputData.TaggedData[0].Data);
			for (int32 I = 0; I < Points->GetNumPoints(); ++I)
			{
				const FPCGPoint Point = FConstPCGPointValueRanges(Points).GetPoint(I);
				const int32* Seed = RemainingSeeds.Find(Point.Transform.GetLocation());
				UTEST_NOT_NULL("Each whole-volume centre appears in only one cell", Seed);
				TestEqual(TEXT("Cell preserves the whole-volume seed"), Point.Seed, *Seed);
				TestEqual(TEXT("Cell boundaries do not attenuate density"), Point.Density, 1.0f);
				RemainingSeeds.Remove(Point.Transform.GetLocation());
			}
		}
		TestTrue(TEXT("Cells retain all whole-volume points, including away from the seam"), RemainingSeeds.IsEmpty());
	}
	// Independent no-operation inputs: do not multiply these by all grid/crop cases.
	for (int32 Case = 0; Case < 4; ++Case)
	{
		auto* Surface = NewObject<UForestPCGAreaSamplerTestSurface>();
		auto* Bounds = NewObject<UPCGVolumeData>();
		Bounds->Initialize(Case == 1 ? FBox(ForceInit) : Surface->Bounds);
		auto* Region = NewObject<UPCGVolumeData>();
		Region->Initialize(Surface->Bounds);
		auto* Tiles = NewObject<UPCGPointData>();
		if (Case != 0)
		{
			Tiles->GetMutablePoints().Emplace_GetRef().SetLocalBounds(Surface->Bounds);
		}
		auto* Settings = NewObject<UForestPCGAreaSamplerSettings>();
		Settings->bUseLegacyGridCreationMethod = true;
		Settings->PointsPerSquaredMeter = Case == 2 ? 0.0f : 0.047f;
		if (Case == 3)
		{
			AddExpectedError(TEXT("Supply one exact spatial Region"), EAutomationExpectedErrorFlags::Contains, 1);
		}
		auto Empty = RunSampler(Settings, Surface, Bounds, Case == 3 ? nullptr : Region, Tiles);
		UTEST_EQUAL("Empty tiles/invalid bounds/zero Ratio/missing Region retain one output", Empty->OutputData.TaggedData.Num(), 1);
		const auto& Tagged = Empty->OutputData.TaggedData[0];
		const auto* Points = Cast<UPCGBasePointData>(Tagged.Data);
		UTEST_NOT_NULL("Empty point data", Points);
		TestEqual(TEXT("No-operation point count"), Points->GetNumPoints(), 0);
		TestTrue(TEXT("No-operation tags"), Tagged.Tags.Contains(TEXT("GEN:Identity")));
		TestTrue(TEXT("No-operation container follows stock factory"), Points->GetClass() == FPCGContext::GetDefaultPointDataClass().Get());
		if (Case == 1 || Case == 2)
		{
			auto* StockSettings = NewObject<UPCGSurfaceSamplerSettings>();
			StockSettings->bUseLegacyGridCreationMethod = true;
			StockSettings->PointsPerSquaredMeter = Settings->PointsPerSquaredMeter;
			auto StockEmpty = RunSampler(StockSettings, Surface, Bounds, nullptr, nullptr);
			UTEST_EQUAL("Stock no-operation datum count", StockEmpty->OutputData.TaggedData.Num(), Empty->OutputData.TaggedData.Num());
			const auto* StockData = Cast<UPCGBasePointData>(StockEmpty->OutputData.TaggedData[0].Data);
			UTEST_NOT_NULL("Stock empty point data", StockData);
			TestEqual(TEXT("Stock no-operation point count"), StockData->GetNumPoints(), Points->GetNumPoints());
			TestTrue(TEXT("Stock no-operation tags"), StockEmpty->OutputData.TaggedData[0].Tags.Num() == Tagged.Tags.Num()
				&& StockEmpty->OutputData.TaggedData[0].Tags.Contains(TEXT("GEN:Identity")));
		}
	}
	return true;
}
#endif
