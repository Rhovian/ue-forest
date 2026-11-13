#include "MeasureLibrary.h"
#include "Components/InstancedSkinnedMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "WorldPartition/WorldPartitionSubsystem.h"

#if WITH_EDITOR
#include "Editor.h"
#include "Settings/LevelEditorPlaySettings.h"
#endif

void UMeasureLibrary::StartPIEInNewWindow(int32 Width, int32 Height)
{
#if WITH_EDITOR
	ULevelEditorPlaySettings* Settings = GetMutableDefault<ULevelEditorPlaySettings>();
	Settings->NewWindowWidth = Width;
	Settings->NewWindowHeight = Height;

	// No DestinationSlateViewport: PIE opens in a new window sized from the settings above.
	FRequestPlaySessionParams Params;
	Params.WorldType = EPlaySessionWorldType::PlayInEditor;
	GEditor->RequestPlaySession(Params);
#endif
}

bool UMeasureLibrary::IsStreamingCompleted(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull);
	UWorldPartitionSubsystem* Partition = World ? World->GetSubsystem<UWorldPartitionSubsystem>() : nullptr;
	return !Partition || Partition->IsAllStreamingCompleted();
}

void UMeasureLibrary::CountLoaded(const UObject* WorldContextObject, int32& Actors, int32& Components, int64& RenderInstances)
{
	Actors = Components = 0;
	RenderInstances = 0;
	UWorld* World = GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull);
	if (!World) return;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		++Actors;
		It->ForEachComponent<UInstancedStaticMeshComponent>(false, [&](const UInstancedStaticMeshComponent* Component)
		{
			++Components;
			RenderInstances += Component->GetNumRenderInstances();
		});
		It->ForEachComponent<UInstancedSkinnedMeshComponent>(false, [&](const UInstancedSkinnedMeshComponent* Component)
		{
			++Components;
			RenderInstances += Component->GetInstanceCount();
		});
	}
}
