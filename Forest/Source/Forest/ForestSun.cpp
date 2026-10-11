#include "ForestSun.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "SunPosition.h"

static constexpr float SecondsPerMinute = 60.0f;
static constexpr float MinutesPerHour = 60.0f;

static FAutoConsoleCommandWithWorldAndArgs TimeCommand(
	TEXT("Forest.Time"), TEXT("Set local hour."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!World || Args.Num() != 1 || !Args[0].IsNumeric()) return;
		for (TActorIterator<AForestSun> It(World); It; ++It) It->SetSolarTime(FCString::Atof(*Args[0]));
	}));

static FAutoConsoleCommandWithWorldAndArgs PauseCommand(
	TEXT("Forest.Pause"), TEXT("Toggle sun clock pause."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (!World) return;
		for (TActorIterator<AForestSun> It(World); It; ++It) It->bPaused = !It->bPaused;
	}));

AForestSun::AForestSun()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AForestSun::BeginPlay()
{
	Super::BeginPlay();
	const FTimespan Time = FTimespan::FromHours(SolarTime);
	FSunPositionData Data;
	USunPositionFunctionLibrary::GetSunPosition(Latitude, Longitude, TimeZone, bDaylightSaving, Year, Month, Day,
		Time.GetHours(), Time.GetMinutes(), Time.GetSeconds(), Data);
	Sunrise = Data.SunriseTime.GetTotalHours();
	Sunset = Data.SunsetTime.GetTotalHours();
	LastAppliedTime = -1.0f;
	ApplySolarTime();
}

void AForestSun::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bPaused && DaylightMinutes > 0.0f)
	{
		SolarTime += DeltaSeconds * (Sunset - Sunrise) / (DaylightMinutes * SecondsPerMinute);
		if (SolarTime > Sunset) SolarTime = Sunrise;
	}
	ApplySolarTime();
}

void AForestSun::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	LastAppliedTime = -1.0f;
	ApplySolarTime();
}

void AForestSun::ApplySolarTime()
{
	if (!Sun) return;
	const float StepHours = StepMinutes / MinutesPerHour;
	const float Hour = StepMinutes > 0.0f ? FMath::FloorToFloat(SolarTime / StepHours) * StepHours : SolarTime;
	if (Hour == LastAppliedTime) return;
	const FTimespan Time = FTimespan::FromHours(Hour);
	FSunPositionData Data;
	USunPositionFunctionLibrary::GetSunPosition(Latitude, Longitude, TimeZone, bDaylightSaving, Year, Month, Day,
		Time.GetHours(), Time.GetMinutes(), Time.GetSeconds(), Data);
	Sun->SetActorRotation(FRotator(-Data.CorrectedElevation, Data.Azimuth + 90.0f, 0.0f));
	LastAppliedTime = Hour;
}
