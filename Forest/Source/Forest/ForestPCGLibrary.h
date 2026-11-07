#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
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
};
