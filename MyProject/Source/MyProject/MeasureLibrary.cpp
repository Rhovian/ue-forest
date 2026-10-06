// Copyright Epic Games, Inc. All Rights Reserved.

#include "MeasureLibrary.h"

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
