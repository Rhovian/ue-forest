#include "ForestSkinnedTickSubsystem.h"
#include "Components/InstancedSkinnedMeshComponent.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"

static FAutoConsoleCommandWithWorldAndArgs SkinnedTickCommand(
	TEXT("Forest.SkinnedTick"), TEXT("0 stops the tick of placed instanced skinned meshes (the default), 1 restores it."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!World || Args.Num() != 1 || !Args[0].IsNumeric()) return;
		if (UForestSkinnedTickSubsystem* Subsystem = World->GetSubsystem<UForestSkinnedTickSubsystem>())
		{
			Subsystem->SetTicking(FCString::Atoi(*Args[0]) != 0);
		}
	}));

bool UForestSkinnedTickSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UForestSkinnedTickSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	// Streamed-in World Partition cells arrive here, after their actors have begun play.
	LevelAddedHandle = FWorldDelegates::LevelAddedToWorld.AddUObject(this, &UForestSkinnedTickSubsystem::OnLevelAdded);
	// UWorld::OnWorldBeginPlay, not the subsystem's own OnWorldBeginPlay: that one runs before the actors begin play,
	// and beginning play registers each tick function enabled again.
	BeginPlayHandle = GetWorld()->OnWorldBeginPlay.AddUObject(this, &UForestSkinnedTickSubsystem::ApplyToLoadedLevels);
}

void UForestSkinnedTickSubsystem::Deinitialize()
{
	FWorldDelegates::LevelAddedToWorld.Remove(LevelAddedHandle);
	if (UWorld* World = GetWorld()) World->OnWorldBeginPlay.Remove(BeginPlayHandle);
	Super::Deinitialize();
}

void UForestSkinnedTickSubsystem::SetTicking(const bool bEnabled)
{
	bTicking = bEnabled;
	ApplyToLoadedLevels();
}

void UForestSkinnedTickSubsystem::ApplyToLoadedLevels() const
{
	for (const ULevel* Level : GetWorld()->GetLevels()) Apply(Level);
}

void UForestSkinnedTickSubsystem::OnLevelAdded(ULevel* Level, UWorld* World)
{
	if (World == GetWorld()) Apply(Level);
}

void UForestSkinnedTickSubsystem::Apply(const ULevel* Level) const
{
	if (!Level) return;
	for (const AActor* Actor : Level->Actors)
	{
		if (!Actor) continue;
		Actor->ForEachComponent<UInstancedSkinnedMeshComponent>(false, [this](UInstancedSkinnedMeshComponent* Component)
		{
			// Both: the first covers a component that registers its tick function after this, the second one that has.
			Component->PrimaryComponentTick.bStartWithTickEnabled = bTicking;
			Component->SetComponentTickEnabled(bTicking);
		});
	}
}
