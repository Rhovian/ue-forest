#include "ForestShadowCacheSubsystem.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Level.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "Streaming/LevelStreamingDelegates.h"

static FAutoConsoleCommandWithWorldAndArgs CachedPlantShadowsCommand(
	TEXT("Forest.CachedPlantShadows"),
	TEXT("1 lets small placed static plants keep cached shadows (the default), 0 restores per-frame invalidation."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!World || Args.Num() != 1 || !Args[0].IsNumeric()) return;
		if (UForestShadowCacheSubsystem* Subsystem = World->GetSubsystem<UForestShadowCacheSubsystem>())
		{
			Subsystem->SetCached(FCString::Atoi(*Args[0]) != 0);
		}
	}));

bool UForestShadowCacheSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UForestShadowCacheSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// Fires at the start of UWorld::AddToWorld, before the level's components register, so the setting is in place when
	// their render state is first created and streaming a cell in costs nothing extra.
	VisibleHandle = FLevelStreamingDelegates::OnLevelBeginMakingVisible.AddUObject(
		this, &UForestShadowCacheSubsystem::OnLevelBeginMakingVisible);
}

void UForestShadowCacheSubsystem::Deinitialize()
{
	FLevelStreamingDelegates::OnLevelBeginMakingVisible.Remove(VisibleHandle);
	Super::Deinitialize();
}

void UForestShadowCacheSubsystem::SetCached(const bool bEnabled)
{
	bCached = bEnabled;
	for (const ULevel* Level : GetWorld()->GetLevels()) Apply(Level);
}

void UForestShadowCacheSubsystem::OnLevelBeginMakingVisible(UWorld* World, const ULevelStreaming*, ULevel* Level)
{
	if (World == GetWorld()) Apply(Level);
}

void UForestShadowCacheSubsystem::Apply(const ULevel* Level) const
{
	if (!Level) return;
	const EShadowCacheInvalidationBehavior Wanted =
		bCached ? EShadowCacheInvalidationBehavior::Static : EShadowCacheInvalidationBehavior::Auto;
	for (const AActor* Actor : Level->Actors)
	{
		if (!Actor) continue;
		Actor->ForEachComponent<UInstancedStaticMeshComponent>(false, [Wanted](UInstancedStaticMeshComponent* Component)
		{
			const UStaticMesh* Mesh = Component->GetStaticMesh();
			if (!Mesh || Mesh->GetBounds().SphereRadius > MaxRadius) return;
			if (Component->ShadowCacheInvalidationBehavior == Wanted) return;
			Component->ShadowCacheInvalidationBehavior = Wanted;
			Component->MarkRenderStateDirty();  // a no-op before the component has registered
		});
	}
}
