#include "../ForestPCGLibrary.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Data/PCGPointArrayData.h"
#include "Misc/AutomationTest.h"
#include "PCGComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForestGeneratedLocationsTest, "Forest.PCG.UniqueGeneratedLocations",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForestGeneratedLocationsTest::RunTest(const FString& Parameters)
{
	UPCGComponent* Component = NewObject<UPCGComponent>();
	auto& Output = const_cast<FPCGDataCollection&>(Component->GetGeneratedGraphOutput());
	const FString Tag = TEXT("GEN:Trees");
	const TArray<FVector> Expected = {FVector(0, 2, 3), FVector(0.001, 2, 3), FVector(0, 2, 4)};
	auto AddPoints = [&](const TArray<FVector>& Positions, const FString& OutputTag, const FString& Role)
	{
		UPCGPointArrayData* Data = NewObject<UPCGPointArrayData>();
		Data->SetNumPoints(Positions.Num());
		auto Transforms = Data->GetTransformValueRange();
		for (int32 Index = 0; Index < Positions.Num(); ++Index)
		{
			Transforms[Index] = FTransform(Positions[Index]);
		}
		FPCGTaggedData& Tagged = Output.TaggedData.Emplace_GetRef();
		Tagged.Data = Data;
		Tagged.Tags.Add(OutputTag);
		Tagged.Tags.Add(Role);
		Tagged.Pin = TEXT("GeneratedPoints");
	};
	AddPoints({Expected[0], FVector(-0.0, 2, 3), Expected[1]}, Tag, TEXT("Root"));
	AddPoints({Expected[0], Expected[2]}, Tag, TEXT("Root")); // Overlapping root data must still be unique.
	AddPoints({FVector(9, 9, 9)}, TEXT("GEN:Veterans"), TEXT("Root"));
	// Core children inherit GEN:Trees: both co-located moss and offset children must be excluded.
	AddPoints({Expected[0], FVector(10, 2, 3)}, Tag, TEXT("Child"));
	AddPoints({FVector(20, 2, 3)}, Tag, TEXT("Other"));
	FPCGTaggedData& NonPoint = Output.TaggedData.Emplace_GetRef();
	NonPoint.Tags.Add(Tag);
	TestTrue(TEXT("Unique root XYZ in first-seen order; co-located and offset children excluded"),
		UForestPCGLibrary::GetGeneratedPointLocations(Component, Tag) == Expected);
	TestTrue(TEXT("Missing tag"), UForestPCGLibrary::GetGeneratedPointLocations(Component, TEXT("missing")).IsEmpty());
	TestTrue(TEXT("Null component"), UForestPCGLibrary::GetGeneratedPointLocations(nullptr, Tag).IsEmpty());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForestClearGeneratedGraphOutputTest, "Forest.PCG.ClearGeneratedGraphOutput",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForestClearGeneratedGraphOutputTest::RunTest(const FString& Parameters)
{
	UPCGComponent* Component = NewObject<UPCGComponent>();
	UPCGComponent* OtherComponent = NewObject<UPCGComponent>();
	auto& Output = const_cast<FPCGDataCollection&>(Component->GetGeneratedGraphOutput());
	auto& OtherOutput = const_cast<FPCGDataCollection&>(OtherComponent->GetGeneratedGraphOutput());
	UPCGPointArrayData* Data = NewObject<UPCGPointArrayData>(Component);
	UPCGPointArrayData* OtherData = NewObject<UPCGPointArrayData>(OtherComponent);
	Output.TaggedData.Emplace_GetRef().Data = Data;
	OtherOutput.TaggedData.Emplace_GetRef().Data = OtherData;
	Output.MarkUsage(EPCGDataUsage::ComponentOutputData);
	OtherOutput.MarkUsage(EPCGDataUsage::ComponentOutputData);

	UForestPCGLibrary::ClearGeneratedGraphOutput(Component);
	TestTrue(TEXT("Given component's output is cleared"), Output.TaggedData.IsEmpty());
	TestFalse(TEXT("Dropped output usage is cleared"), Data->HasUsage(EPCGDataUsage::ComponentOutputData));
	TestTrue(TEXT("Other output data and usage are untouched"), OtherOutput.TaggedData.Num() == 1
		&& OtherOutput.TaggedData[0].Data.Get() == OtherData && OtherData->HasUsage(EPCGDataUsage::ComponentOutputData));
	UForestPCGLibrary::ClearGeneratedGraphOutput(nullptr); // Must return without dereferencing null.
	OtherOutput.ClearUsage(EPCGDataUsage::ComponentOutputData);
	return true;
}
#endif
