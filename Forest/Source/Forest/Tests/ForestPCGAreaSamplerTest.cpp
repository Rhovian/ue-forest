#include "../ForestPCGAreaSampler.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ForestPCGAreaSamplerTestData.h"
#include "Data/PCGPointData.h"
#include "Data/PCGVolumeData.h"
#include "Elements/PCGSurfaceSampler.h"
#include "Misc/AutomationTest.h"
#include "PCGContext.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForestAreaSamplerIdentityTest, "Forest.PCG.AreaSampler.Identity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForestAreaSamplerIdentityTest::RunTest(const FString& Parameters)
{
	// No existing project sampler test: UniqueGeneratedLocations covers only output collection.
	// Each mode needs full and cropped comparisons: cropping changes Ratio only in legacy mode.
	for (const bool bLegacy : {false, true})
	{
		UForestPCGAreaSamplerTestSurface* Surface = NewObject<UForestPCGAreaSamplerTestSurface>();
		Surface->Metadata->CreateAttribute<double>(TEXT("Elevation"), -1, false, false);
		Surface->Metadata->CreateAttribute<int32>(TEXT("SurfaceKind"), 247, false, false);
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

		auto Run = [](UPCGSettings* Settings, const UPCGSpatialData* InSurface,
			const UPCGSpatialData* InBounds, const UPCGSpatialData* Region, const UPCGPointData* Tiles)
		{
			FPCGDataCollection Inputs;
			auto Add = [&](const UPCGData* Data, FName Pin)
			{
				if (!Data) { return; }
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
			while (!Element->Execute(Context.Get())) {}
			return Context;
		};
		auto Stock = Run(StockSettings, Surface, Bounds, nullptr, nullptr);
		UTEST_EQUAL("One stock surface output", Stock->OutputData.TaggedData.Num(), 1);
		const UPCGPointData* StockPoints = Cast<UPCGPointData>(Stock->OutputData.TaggedData[0].Data);
		// Force the stock reference to the same legacy container through the public helper if the CVar uses arrays.
		const UPCGSpatialData* StockSpatial = CastChecked<UPCGSpatialData>(Stock->OutputData.TaggedData[0].Data);
		if (!StockPoints) { StockPoints = StockSpatial->ToPointData(Stock.Get()); }
		UTEST_NOT_NULL("Stock points", StockPoints);
		TestTrue(TEXT("Non-empty reference"), StockPoints->GetPoints().Num() > 10);
		const int32 FullProjections = Surface->Projections;

		UForestPCGAreaSamplerSettings* AreaSettings = NewObject<UForestPCGAreaSamplerSettings>();
		AreaSettings->Seed = StockSettings->Seed;
		AreaSettings->bUseLegacyGridCreationMethod = bLegacy;
		AreaSettings->PointsPerSquaredMeter = StockSettings->PointsPerSquaredMeter;
		AreaSettings->PointExtents = StockSettings->PointExtents;
		AreaSettings->Looseness = StockSettings->Looseness;
		AreaSettings->PointSteepness = StockSettings->PointSteepness;
		AreaSettings->bApplyDensityToPoints = StockSettings->bApplyDensityToPoints;
		for (const bool bCrop : {false, true})
		{
			// A tight crop around a known stock sample also catches omitting cells whose origins
			// are outside the crop but whose jittered samples enter it. Non-empty by construction.
			const FVector Centre = StockPoints->GetPoints()[StockPoints->GetPoints().Num() / 2].Transform.GetLocation();
			const FBox RegionBox = bCrop
				? FBox(Centre - FVector(1, 1, 1000), Centre + FVector(1, 1, 1000)) : Surface->Bounds;
			UPCGVolumeData* Region = NewObject<UPCGVolumeData>();
			Region->Initialize(RegionBox);
			UPCGPointData* Tiles = NewObject<UPCGPointData>();
			// Reversed, overlapping tiles: no duplicates, preserve stock Y/X ordering.
			const double Overlap = bCrop ? 0.1 : 50.0;
			for (const double CentreX : {RegionBox.GetCenter().X + Overlap, RegionBox.GetCenter().X - Overlap})
			{
				FPCGPoint& Tile = Tiles->GetMutablePoints().Emplace_GetRef();
				Tile.Transform.SetLocation(FVector(CentreX, RegionBox.GetCenter().Y, 0));
				Tile.SetExtents(RegionBox.GetExtent() + FVector(Overlap, 0, 0));
			}
			Surface->Projections = 0;
			auto Area = Run(AreaSettings, Surface, Bounds, Region, Tiles);
			UTEST_EQUAL("One area surface output", Area->OutputData.TaggedData.Num(), 1);
			const UPCGPointData* Actual = Cast<UPCGPointData>(Area->OutputData.TaggedData[0].Data);
			UTEST_NOT_NULL("Area points", Actual);
			TestTrue(TEXT("Tags retained"), Area->OutputData.TaggedData[0].Tags.Contains(TEXT("GEN:Identity")));
			TestEqual(TEXT("Output pin"), Area->OutputData.TaggedData[0].Pin, PCGPinConstants::DefaultOutputLabel);
			TArray<FPCGPoint> Expected;
			for (const FPCGPoint& Point : StockPoints->GetPoints())
			{
				FPCGPoint Sample;
				if (Region->SamplePoint(Point.Transform, FBox(FVector::ZeroVector, FVector::ZeroVector), Sample, nullptr)
					&& Sample.Density > 0) { Expected.Add(Point); }
			}
			TestTrue(TEXT("Crop is a strict non-empty subset"), !bCrop || (Expected.Num() > 0 && Expected.Num() < StockPoints->GetPoints().Num()));
			TestTrue(TEXT("Full region covers every stock point"), bCrop || Expected.Num() == StockPoints->GetPoints().Num());
			UTEST_EQUAL("Exact subset count", Actual->GetPoints().Num(), Expected.Num());
			const auto* StockAttribute = StockPoints->Metadata->GetConstTypedAttribute<double>(TEXT("Elevation"));
			const auto* AreaAttribute = Actual->Metadata->GetConstTypedAttribute<double>(TEXT("Elevation"));
			UTEST_NOT_NULL("Stock attribute", StockAttribute);
			UTEST_NOT_NULL("Area attribute", AreaAttribute);
			const auto* Inherited = Actual->Metadata->GetConstTypedAttribute<int32>(TEXT("SurfaceKind"));
			UTEST_NOT_NULL("Inherited surface attribute", Inherited);
			TestEqual(TEXT("Inherited default value"), Inherited->GetValueFromItemKey(PCGInvalidEntryKey), 247);
			for (int32 I = 0; I < Expected.Num(); ++I)
			{
				const FPCGPoint& A = Actual->GetPoints()[I];
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
		}
	}
	return true;
}
#endif
