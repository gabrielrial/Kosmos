
def brightness_to_mode(brightness: float) -> bool:
    if brightness > 0.5:
        return True
    else:
        return False

def color_to_note(colors: list[int], brightness: float) -> int:
    
