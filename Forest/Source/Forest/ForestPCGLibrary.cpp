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
	for (const FPCGTaggedData& Tagged : Component->GetGeneratedGraphOutput().TaggedData)
	{
		const UPCGBasePointData* Points = Cast<UPCGBasePointData>(Tagged.Data.Get());
		if (Points && Tagged.Tags.Contains(Tag))
		{
			for (const FTransform& Transform : Points->GetConstTransformValueRange())
			{
				Locations.Add(Transform.GetLocation());
			}
		}
	}
	return Locations;
}
