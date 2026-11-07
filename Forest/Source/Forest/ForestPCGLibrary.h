#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"

class UPCGComponent;
#include "ForestPCGLibrary.generated.h"

/** PCG hooks for scripts/pcg that the engine does not expose to Python. */
UCLASS()
class UForestPCGLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Cancels every running PCG generation in the current world (UPCGSubsystem::CancelAllGeneration); returns false
	 *  when there is no PCG subsystem. scripts/pcg/regenerate_biome.py calls it when a regenerate passes its memory
	 *  limit. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static bool CancelAllPCGGeneration();

	/** World locations of the points a PCG component generated under every output tagged Tag (Biome Core tags each
	 *  group's GeneratedPoints "GEN:<group>", e.g. "GEN:Trees"). Python cannot read PCG point data or GPU-only skinned
	 *  instances; scripts/pcg/canopy_gaps.py finds canopy gaps from the trees' points. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static TArray<FVector> GetGeneratedPointLocations(const UPCGComponent* Component, const FString& Tag);
};
