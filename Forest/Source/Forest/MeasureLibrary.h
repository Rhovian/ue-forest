#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "MeasureLibrary.generated.h"

/** Editor hooks for scripts/measure, which Python cannot reach otherwise. */
UCLASS()
class UMeasureLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Starts PIE in a new window of a fixed size, so measurements do not depend on the editor layout. */
	UFUNCTION(BlueprintCallable, Category = "Measure", meta = (DevelopmentOnly))
	static void StartPIEInNewWindow(int32 Width, int32 Height);

	/** True once World Partition has finished streaming levels in and out of the world the context object is in
	 *  (UWorldPartitionSubsystem::IsAllStreamingCompleted, which Python cannot reach: it has no way to get a world
	 *  subsystem). True for a world without World Partition. */
	UFUNCTION(BlueprintCallable, Category = "Measure", meta = (WorldContext = "WorldContextObject"))
	static bool IsStreamingCompleted(const UObject* WorldContextObject);

	/** What is loaded in the world the context object is in: its actors, their instanced mesh components (static and
	 *  skinned), and the instances those render. Render instances, not GetInstanceCount: a landscape grass component
	 *  keeps its instance array empty and reports its built instances only through GetNumRenderInstances, so this is
	 *  the count that changes when a grass build is accepted. scripts/measure waits for all three to hold still. */
	UFUNCTION(BlueprintCallable, Category = "Measure", meta = (WorldContext = "WorldContextObject"))
	static void CountLoaded(const UObject* WorldContextObject, int32& Actors, int32& Components, int64& RenderInstances);
};
