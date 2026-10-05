// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SmokeActor.generated.h"

class USceneComponent;

UCLASS()
class MYPROJECT_API ASmokeActor : public AActor
{
	GENERATED_BODY()

public:
	ASmokeActor();

	UPROPERTY(VisibleAnywhere)
	TObjectPtr<USceneComponent> Root;
};
