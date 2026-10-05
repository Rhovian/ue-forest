// Copyright Epic Games, Inc. All Rights Reserved.

#include "SmokeActor.h"
#include "Components/SceneComponent.h"

ASmokeActor::ASmokeActor()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
}
