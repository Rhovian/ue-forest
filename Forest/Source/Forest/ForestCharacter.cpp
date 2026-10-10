#include "ForestCharacter.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"

AForestCharacter::AForestCharacter()
{
	GetCapsuleComponent()->InitCapsuleSize(34.0f, 96.0f);
	bUseControllerRotationYaw = true;
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(GetCapsuleComponent());
	Camera->SetRelativeLocation(FVector(0.0f, 0.0f, 64.0f));
	Camera->bUsePawnControlRotation = true;
}

void AForestCharacter::CreateInputMappings()
{
	if (MappingContext) return;
	MappingContext = NewObject<UInputMappingContext>(this);
	MoveAction = NewObject<UInputAction>(this);
	MoveAction->ValueType = EInputActionValueType::Axis2D;
	MoveAction->AccumulationBehavior = EInputActionAccumulationBehavior::Cumulative;
	LookAction = NewObject<UInputAction>(this);
	LookAction->ValueType = EInputActionValueType::Axis2D;
	JumpAction = NewObject<UInputAction>(this);
	JumpAction->ValueType = EInputActionValueType::Boolean;
	SprintAction = NewObject<UInputAction>(this);
	SprintAction->ValueType = EInputActionValueType::Boolean;

	UInputModifierSwizzleAxis* ForwardAxis = NewObject<UInputModifierSwizzleAxis>(MappingContext);
	ForwardAxis->Order = EInputAxisSwizzle::YXZ;
	UInputModifierNegate* Negative = NewObject<UInputModifierNegate>(MappingContext);
	MappingContext->MapKey(MoveAction, EKeys::W).Modifiers.Add(ForwardAxis);
	MappingContext->MapKey(MoveAction, EKeys::S).Modifiers = { Negative, ForwardAxis };
	MappingContext->MapKey(MoveAction, EKeys::D);
	MappingContext->MapKey(MoveAction, EKeys::A).Modifiers.Add(Negative);
	MappingContext->MapKey(LookAction, EKeys::Mouse2D);
	MappingContext->MapKey(JumpAction, EKeys::SpaceBar);
	MappingContext->MapKey(SprintAction, EKeys::LeftShift);
}

void AForestCharacter::PawnClientRestart()
{
	CreateInputMappings(); // Super creates and binds the input component.
	Super::PawnClientRestart();
	GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
	if (InputSubsystem.IsValid()) InputSubsystem->RemoveMappingContext(MappingContext);
	InputSubsystem.Reset();
	if (APlayerController* PC = Cast<APlayerController>(GetController()); PC && PC->IsLocalController())
	{
		InputSubsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer());
		if (InputSubsystem.IsValid()) InputSubsystem->AddMappingContext(MappingContext, 0);
	}
}

void AForestCharacter::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (InputSubsystem.IsValid()) InputSubsystem->RemoveMappingContext(MappingContext);
	Super::EndPlay(EndPlayReason);
}

void AForestCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	CreateInputMappings();
	if (UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent))
	{
		Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AForestCharacter::Move);
		Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &AForestCharacter::Look);
		Input->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
		Input->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
		Input->BindAction(JumpAction, ETriggerEvent::Canceled, this, &ACharacter::StopJumping);
		Input->BindAction(SprintAction, ETriggerEvent::Triggered, this, &AForestCharacter::Sprint);
		Input->BindAction(SprintAction, ETriggerEvent::Completed, this, &AForestCharacter::Sprint);
		Input->BindAction(SprintAction, ETriggerEvent::Canceled, this, &AForestCharacter::Sprint);
	}
}

void AForestCharacter::Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	AddMovementInput(GetActorForwardVector(), Axis.Y);
	AddMovementInput(GetActorRightVector(), Axis.X);
}

void AForestCharacter::Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	AddControllerYawInput(Axis.X);
	// MouseY is positive upwards; the default controller's legacy pitch scale is negative.
	AddControllerPitchInput(-Axis.Y);
}

void AForestCharacter::Sprint(const FInputActionValue& Value)
{
	GetCharacterMovement()->MaxWalkSpeed = Value.Get<bool>() ? SprintSpeed : WalkSpeed;
}
