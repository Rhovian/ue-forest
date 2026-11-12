#pragma once

#include "Subsystems/WorldSubsystem.h"
#include "ForestSkinnedTickSubsystem.generated.h"

class ULevel;

/** Stops the per-frame tick of placed instanced skinned meshes (the Megaplants) in game worlds. Their wind runs on the
 *  GPU (Dynamic Wind). The tick only refreshes bounds and re-sends render data
 *  (UInstancedSkinnedMeshComponent::RefreshBoneTransforms), at about 0.09 ms of game thread time per 1,000 loaded
 *  instances: 41 of 50 ms at the interior route point (#206). `Forest.SkinnedTick 1` restores the ticks for comparison. */
UCLASS()
class UForestSkinnedTickSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Sets the tick of every instanced skinned mesh component in the loaded levels, and in levels streamed in later. */
	void SetTicking(bool bEnabled);

protected:
	virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
	void ApplyToLoadedLevels() const;
	void OnLevelAdded(ULevel* Level, UWorld* World);
	void Apply(const ULevel* Level) const;

	FDelegateHandle LevelAddedHandle;
	FDelegateHandle BeginPlayHandle;
	bool bTicking = false;
};
