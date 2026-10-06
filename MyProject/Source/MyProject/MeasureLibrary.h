// Copyright Epic Games, Inc. All Rights Reserved.

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
};
