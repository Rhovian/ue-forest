#pragma once

#include "GameFramework/Actor.h"
#include "ForestSun.generated.h"

class ADirectionalLight;

UCLASS()
class AForestSun : public AActor
{
	GENERATED_BODY()

public:
	AForestSun();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnConstruction(const FTransform& Transform) override;
	void SetSolarTime(float Time) { SolarTime = Time; ApplySolarTime(); }

	UPROPERTY(EditAnywhere, Category = "Sun")
	TObjectPtr<ADirectionalLight> Sun;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float Latitude = 54.33f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float Longitude = 13.55f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float TimeZone = 1.0f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	bool bDaylightSaving = true;
	UPROPERTY(EditAnywhere, Category = "Sun")
	int32 Year = 2026;
	UPROPERTY(EditAnywhere, Category = "Sun")
	int32 Month = 6;
	UPROPERTY(EditAnywhere, Category = "Sun")
	int32 Day = 21;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float SolarTime = 10.0f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float DaylightMinutes = 20.0f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	float StepMinutes = 0.0f;
	UPROPERTY(EditAnywhere, Category = "Sun")
	bool bPaused = false;

private:
	float Sunrise = 0.0f;
	float Sunset = 0.0f;
	float LastAppliedTime = -1.0f;
	void ApplySolarTime();
};
