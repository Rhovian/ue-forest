#pragma once

#include "Subsystems/WorldSubsystem.h"
#include "ForestShadowCacheSubsystem.generated.h"

class ULevel;
class ULevelStreaming;

/** Lets the small placed static plants keep their cached shadows in game worlds. Their materials sway them with World
 *  Position Offset, which by default invalidates every virtual shadow map page they touch, every frame: with 760,000
 *  ferns loaded that redraws the whole shadow map (#216). Set to Static, a plant still sways and still casts its shadow;
 *  the shadow no longer moves with it. Meshes larger than MaxRadius (the static trees) are left alone, because a still
 *  shadow under a moving crown shows. `Forest.CachedPlantShadows 0` restores the default for comparison. */
UCLASS()
class UForestShadowCacheSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** Applies the setting to every loaded level, re-creating render state where it changes, and to levels streamed in
	 *  later. */
	void SetCached(bool bEnabled);

protected:
	virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
	void OnLevelBeginMakingVisible(UWorld* World, const ULevelStreaming* Streaming, ULevel* Level);
	void Apply(const ULevel* Level) const;

	/** cm; bounding sphere radius of the mesh. Ferns, flowers, ivy columns, litter, rocks and logs are under it; the
	 *  hornbeams (about 8 m) and the field beech (about 17 m) are over it. */
	static constexpr float MaxRadius = 500.0f;

	FDelegateHandle VisibleHandle;
	bool bCached = true;
};
