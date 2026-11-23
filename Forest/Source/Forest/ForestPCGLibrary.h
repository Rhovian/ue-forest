#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"

class UPCGComponent;
class UPCGGraph;
#include "ForestPCGLibrary.generated.h"

/** PCG hooks for scripts/pcg that the engine does not expose to Python. */
UCLASS()
class UForestPCGLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Cancels every running PCG generation in the current world (UPCGSubsystem::CancelAllGeneration); returns false
	 *  when there is no PCG subsystem. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static bool CancelAllPCGGeneration();

	/** Clears only this component's live graph output; preserves managed resources and per-cell components; null is a no-op.
	 *  Marks the package dirty without regenerating. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static void ClearGeneratedGraphOutput(UPCGComponent* Component);

	/** Unique world locations (exact XYZ, first-seen order) across PCG_ForestPlacement outputs tagged Root and Tag.
	 *  scripts/pcg/placement.py tags each group's root points Root and "GEN:<group>", e.g. "GEN:Trees"; children are excluded,
	 *  including children at offset positions. Python cannot read GPU-only skinned instances;
	 *  scripts/pcg/canopy_gaps.py uses these root locations as trunks. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static TArray<FVector> GetGeneratedPointLocations(const UPCGComponent* Component, const FString& Tag);

	/** Removes a graph user parameter and refreshes its instances in the editor; false for null, absent, or non-editor calls. */
	UFUNCTION(BlueprintCallable, Category = "Forest PCG")
	static bool RemoveGraphUserParameter(UPCGGraph* Graph, FName Name);
};
