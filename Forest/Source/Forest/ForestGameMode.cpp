#include "ForestGameMode.h"
#include "ForestCharacter.h"

AForestGameMode::AForestGameMode()
{
	DefaultPawnClass = AForestCharacter::StaticClass();
}
