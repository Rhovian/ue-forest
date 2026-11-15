#include "ForestPCGLibrary.h"

#include "Data/PCGBasePointData.h"
#include "PCGComponent.h"
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

TArray<FVector> UForestPCGLibrary::GetGeneratedPointLocations(const UPCGComponent* Component, const FString& Tag)
{
	TArray<FVector> Locations;
	if (!Component)
	{
		return Locations;
	}
	// UE 5.8 PCGComponent.cpp::PostProcessGraph stores each output independently; PCGData.h's
	// GetTaggedInputs filters tags only. Distinct point-data objects can contain the same location (#196).
	TSet<FVector> Seen;
	for (const FPCGTaggedData& Tagged : Component->GetGeneratedGraphOutput().TaggedData)
	{
		const UPCGBasePointData* Points = Cast<UPCGBasePointData>(Tagged.Data.Get());
		if (Points && Tagged.Tags.Contains(Tag))
		{
			for (const FTransform& Transform : Points->GetConstTransformValueRange())
			{
				const FVector Location = Transform.GetLocation();
				// FVector's UE 5.8 hash uses raw bytes (Math/Vector.h::GetTypeHash), unlike XYZ equality.
				// Canonicalize signed zero in the key so +0 and -0 occupy the same bucket.
				const FVector Key(Location.X == 0 ? 0.0 : Location.X,
					Location.Y == 0 ? 0.0 : Location.Y, Location.Z == 0 ? 0.0 : Location.Z);
				if (!Seen.Contains(Key))
				{
					Seen.Add(Key);
					Locations.Add(Location);
				}
			}
		}
	}
	return Locations;
}
