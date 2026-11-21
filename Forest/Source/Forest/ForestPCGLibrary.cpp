#include "ForestPCGLibrary.h"

#include "Data/PCGBasePointData.h"
#include "PCGComponent.h"
#include "Subsystems/PCGSubsystem.h"
#include "UObject/UnrealType.h"

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

void UForestPCGLibrary::ClearGeneratedGraphOutput(UPCGComponent* Component)
{
	if (!Component)
	{
		return;
	}
	// UE 5.8 PCGComponent.h:693 makes ClearGraphGeneratedOutput private; cleanup also touches managed resources.
	// PCGComponent.cpp:1920-1926 saves LoadedPreviewGeneratedGraphOutput in Preview mode, so clear both collections.
	const FName OutputNames[] = {
		TEXT("GeneratedGraphOutput"),
#if WITH_EDITORONLY_DATA
		TEXT("LoadedPreviewGeneratedGraphOutput"),
#endif
	};
	for (const FName OutputName : OutputNames)
	{
		FStructProperty* Property = FindFProperty<FStructProperty>(UPCGComponent::StaticClass(), OutputName);
		check(Property && Property->Struct == FPCGDataCollection::StaticStruct());
		FPCGDataCollection* Output = Property->ContainerPtrToValuePtr<FPCGDataCollection>(Component);
		// Match PCGComponent.cpp:1710,1740 without reparenting data potentially shared with other components.
		Output->ClearUsage(EPCGDataUsage::ComponentOutputData);
		Output->Reset();
	}
	Component->MarkPackageDirty();
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
