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

	/** Clears only this component's generated graph output, including its saved preview snapshot; null is a no-op.
	 *  Leaves managed resources and per-cell components untouched, without regenerating. Marks the package dirty;
	 *  scripts/pcg/biome_volume.py uses it before saving the volume after switching to partitioned generation. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static void ClearGeneratedGraphOutput(UPCGComponent* Component);

	/** Unique world locations (exact XYZ, first-seen order) across Biome Core outputs tagged Root and Tag.
	 *  Each group's GeneratedPoints has "GEN:<group>", e.g. "GEN:Trees"; Child outputs share that tag but are excluded,
	 *  including children at offset positions. Python cannot read GPU-only skinned instances;
	 *  scripts/pcg/canopy_gaps.py uses these root locations as trunks. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static TArray<FVector> GetGeneratedPointLocations(const UPCGComponent* Component, const FString& Tag);
};
