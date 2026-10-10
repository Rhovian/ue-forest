#pragma once

#include "GameFramework/Character.h"
#include "ForestCharacter.generated.h"

class UCameraComponent;
class UInputAction;
class UInputMappingContext;
class UEnhancedInputLocalPlayerSubsystem;
struct FInputActionValue;

/** Asset-free first-person pawn for scenery walks. */
UCLASS()
class AForestCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AForestCharacter();
	virtual void PawnClientRestart() override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(EditAnywhere, Category = "Movement")
	float WalkSpeed = 300.0f;
	UPROPERTY(EditAnywhere, Category = "Movement")
	float SprintSpeed = 650.0f;

private:
	UPROPERTY(VisibleAnywhere, Category = "Camera")
	TObjectPtr<UCameraComponent> Camera;
	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> JumpAction;
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> SprintAction;
	TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> InputSubsystem;

	void CreateInputMappings();
	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void Sprint(const FInputActionValue& Value);
};
