#pragma once

#include "PCGSettings.h"
#include "ForestPCGAreaSampler.generated.h"

namespace ForestPCGAreaSampler
{
	const FName TilesLabel = TEXT("Region Tiles");
	const FName RegionLabel = TEXT("Region");
}

/** Stock-compatible lattice sampling restricted by a conservative tile cover and an exact region.
 * Region Tiles: point bounds, transformed to axis-aligned boxes in the PRE-projection grid plane.
 * Their XY footprints must cover every possible pre-projection position accepted by Region.
 * Z is ignored. For landscapes these are ordinary world XY boxes; jitter padding is automatic.
 * Region: spatial predicate at the PROJECTED centre (zero local bounds), density > 0 means inside.
 * Its density/metadata do not modify output. Bounding Shape is sampled at the projected centre; its density is retained.
 * Never replace the original Bounding Shape with Region: legacy Ratio depends on the original bounds.
 */
UCLASS(BlueprintType, ClassGroup = (Procedural))
class UForestPCGAreaSamplerSettings : public UPCGSettings
{
	GENERATED_BODY()
public:
	UForestPCGAreaSamplerSettings();
#if WITH_EDITOR
	virtual FName GetDefaultNodeName() const override
	{
		return TEXT("ForestAreaSampler");
	}
	virtual FText GetDefaultNodeTitle() const override
	{
		return NSLOCTEXT("Forest", "AreaSampler", "Forest Area Sampler");
	}
	virtual EPCGSettingsType GetType() const override
	{
		return EPCGSettingsType::Sampler;
	}
#endif
	virtual bool UseSeed() const override
	{
		return true;
	}

	// Match UPCGSurfaceSamplerSettings, including script property names. Its non-exported constructor
	// prevents subclassing outside PCG (UE 5.8 Public/Elements/PCGSurfaceSampler.h, MinimalAPI).
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (ClampMin = "0", PCG_Overridable))
	float PointsPerSquaredMeter = 0.1f;
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (PCG_Overridable))
	FVector PointExtents = FVector(50);
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (ClampMin = "0", PCG_Overridable))
	float Looseness = 1.0f;
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (PCG_Overridable))
	bool bUnbounded = false;
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (PCG_Overridable))
	bool bApplyDensityToPoints = true;
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (ClampMin = "0", ClampMax = "1", PCG_Overridable))
	float PointSteepness = 0.5f;
	UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = Settings)
	bool bUseLegacyGridCreationMethod = false;
#if WITH_EDITORONLY_DATA
	UPROPERTY(Transient, BlueprintReadWrite, EditAnywhere, Category = Settings, meta = (PCG_Overridable))
	bool bKeepZeroDensityPoints = false;
#endif
protected:
	virtual TArray<FPCGPinProperties> InputPinProperties() const override;
	virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
	virtual FPCGElementPtr CreateElement() const override;
};
