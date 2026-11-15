#include "ForestPCGLibrary.h"

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
	auto AddPoints = [&](const TArray<FVector>& Positions, const FString& OutputTag)
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
		Tagged.Pin = TEXT("GeneratedPoints");
	};
	AddPoints({Expected[0], FVector(-0.0, 2, 3), Expected[1]}, Tag);
	AddPoints({Expected[0], Expected[2]}, Tag); // Distinct data objects can overlap; pointer identity is insufficient.
	AddPoints({FVector(9, 9, 9)}, TEXT("GEN:Veterans"));
	FPCGTaggedData& NonPoint = Output.TaggedData.Emplace_GetRef();
	NonPoint.Tags.Add(Tag);
	TestTrue(TEXT("Unique exact XYZ in first-seen order"),
		UForestPCGLibrary::GetGeneratedPointLocations(Component, Tag) == Expected);
	TestTrue(TEXT("Missing tag"), UForestPCGLibrary::GetGeneratedPointLocations(Component, TEXT("missing")).IsEmpty());
	TestTrue(TEXT("Null component"), UForestPCGLibrary::GetGeneratedPointLocations(nullptr, Tag).IsEmpty());
	return true;
}
#endif
