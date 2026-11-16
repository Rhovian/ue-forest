#pragma once

#include "Data/PCGSurfaceData.h"
#include "Data/PCGVolumeData.h"
#include "Metadata/PCGMetadata.h"
#include "Metadata/PCGMetadataAttributeTpl.h"
#include "ForestPCGAreaSamplerTestData.generated.h"

/** Analytic surface with non-default projected properties and per-point metadata. No world/editor needed. */
UCLASS(Transient)
class UForestPCGAreaSamplerTestSurface : public UPCGSurfaceData
{
	GENERATED_BODY()
public:
	mutable int32 Projections = 0;
	mutable FBox PreparedBounds = FBox(ForceInit);
	mutable bool bOutsidePrepared = false;
	virtual TArray<FPCGTaskId> PrepareForSpatialQuery(FPCGContext* Context, const FBox& InBounds) const override
	{
		PreparedBounds = InBounds;
		bOutsidePrepared = false;
		return {};
	}
	FBox Bounds = FBox(FVector(-1731, -1287, -100), FVector(2199, 1841, 600));
	virtual FBox GetBounds() const override
	{
		return Bounds;
	}
	virtual bool SamplePoint(const FTransform& InTransform, const FBox& InBounds,
		FPCGPoint& OutPoint, UPCGMetadata* OutMetadata) const override
	{
		return ProjectPoint(InTransform, InBounds, {}, OutPoint, OutMetadata);
	}
	virtual bool ProjectPoint(const FTransform& InTransform, const FBox& InBounds,
		const FPCGProjectionParams& Params, FPCGPoint& OutPoint, UPCGMetadata* OutMetadata) const override
	{
		++Projections;
		const FVector P = InTransform.GetLocation();
		bOutsidePrepared |= !PreparedBounds.IsInsideOrOn(P);
		if (P.X > 1900 && P.Y > 1400)
		{
			return false;
		}
		OutPoint.Transform = FTransform(FQuat(FVector::RightVector, 0.13), FVector(P.X, P.Y, 30 + P.X * 0.04));
		OutPoint.Transform.SetScale3D(FVector(1.1, 0.9, 1.2));
		OutPoint.Color = FVector4(0.2, 0.4, 0.6, 0.8);
		OutPoint.SetLocalCenter(FVector(2, 3, 4)); // Stock discards this centre in emitted bounds.
		OutPoint.Density = 0.31f; // Stock deliberately discards projected density.
		if (OutMetadata)
		{
			OutPoint.MetadataEntry = OutMetadata->AddEntry();
			OutMetadata->FindOrCreateAttribute<double>(TEXT("Elevation"), -1, false, false)->SetValue(OutPoint.MetadataEntry, P.X * 0.04);
		}
		return true;
	}
protected:
	virtual UPCGSpatialData* CopyInternal(FPCGContext* Context) const override
	{
		return NewObject<UForestPCGAreaSamplerTestSurface>();
	}
	virtual const UPCGPointData* CreatePointData(FPCGContext* Context) const override
	{
		return nullptr;
	}
};

/** Soft spatial mask used independently for original biome bounds and binary Region membership. */
UCLASS(Transient)
class UForestPCGAreaSamplerTestBounds : public UPCGVolumeData
{
	GENERATED_BODY()
public:
	float InsideDensity = 0.6f;
	bool bCutCorner = true;
	virtual bool SamplePoint(const FTransform& InTransform, const FBox& InBounds,
		FPCGPoint& OutPoint, UPCGMetadata* OutMetadata) const override
	{
		if (!Super::SamplePoint(InTransform, InBounds, OutPoint, OutMetadata))
		{
			return false;
		}
		OutPoint.Density = bCutCorner && InTransform.GetLocation().X + InTransform.GetLocation().Y > 1800 ? 0.0f : InsideDensity;
		return OutPoint.Density > 0;
	}
};
