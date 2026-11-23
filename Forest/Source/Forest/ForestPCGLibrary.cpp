#include "ForestPCGLibrary.h"

#include "Data/PCGBasePointData.h"
#include "PCGComponent.h"
#include "PCGGraph.h"
#include "Subsystems/PCGSubsystem.h"

bool UForestPCGLibrary::CancelAllPCGGeneration()
{
	UPCGSubsystem* Subsystem = UPCGSubsystem::GetSubsystemForCurrentWorld();
	if (!Subsystem)
	{
		return false;
	}
	Subsystem->CancelAllGeneration();
	return true;
}

bool UForestPCGLibrary::RemoveGraphUserParameter(UPCGGraph* Graph, FName Name)
{
#if WITH_EDITOR
	if (!Graph || !Graph->GetUserParametersStruct()->FindPropertyDescByName(Name))
	{
		return false;
	}
	Graph->Modify();
	// UE 5.8 PCGGraph.cpp::UpdateUserParametersStruct notifies child instances after the edit.
	Graph->UpdateUserParametersStruct([Name](FInstancedPropertyBag& Parameters)
	{
		Parameters.RemovePropertyByName(Name);
	});
	return true;
#else
	return false;
#endif
}

void UForestPCGLibrary::ClearGeneratedGraphOutput(UPCGComponent* Component)
{
	if (Component)
	{
		// UPCGComponent::ClearGraphGeneratedOutput is private; cleanup also touches managed resources.
		auto& Output = const_cast<FPCGDataCollection&>(Component->GetGeneratedGraphOutput());
		Output.ClearUsage(EPCGDataUsage::ComponentOutputData);
		Output.Reset();
		Component->MarkPackageDirty();
	}
}

TArray<FVector> UForestPCGLibrary::GetGeneratedPointLocations(const UPCGComponent* Component, const FString& Tag)
{
	TArray<FVector> Locations;
	if (!Component)
	{
		return Locations;
	}
	// Biome Core emits Root and Child outputs under the same GEN tag (#196, editor tags probe).
	// Children include moss at the host transform and can have offsets: only Root outputs are trunks.
	TSet<FVector> Seen;
	for (const FPCGTaggedData& Tagged : Component->GetGeneratedGraphOutput().TaggedData)
	{
		const UPCGBasePointData* Points = Cast<UPCGBasePointData>(Tagged.Data.Get());
		if (Points && Tagged.Tags.Contains(Tag) && Tagged.Tags.Contains(TEXT("Root")))
		{
			for (const FTransform& Transform : Points->GetConstTransformValueRange())
			{
				const FVector Location = Transform.GetLocation();
				// FVector's UE 5.8 hash uses raw bytes (Math/Vector.h::GetTypeHash), unlike XYZ equality.
				// Canonicalize signed zero in the key so +0 and -0 occupy the same bucket.
				const FVector Key(Location.X == 0 ? 0.0 : Location.X,
					Location.Y == 0 ? 0.0 : Location.Y, Location.Z == 0 ? 0.0 : Location.Z);
				bool bAlreadySet;
				Seen.Add(Key, &bAlreadySet);
				if (!bAlreadySet)
				{
					Locations.Add(Location);
				}
			}
		}
	}
	return Locations;
}
