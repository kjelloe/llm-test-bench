# white_flash_shot

An automated screenshot of the Unity port shows small white rectangles near burning wrecks at the edge of the frame. The browser screenshot of the same tick shows orange flames there. Before changing any material or texture, what should you check, and why?

A. Whether the flame texture lost its alpha on import, since an opaque white quad means it was imported without alpha; reimport it with alpha.
B. Whether HDR emission clips: values above 1 turn white without tone mapping, so add a tone mapper to the screenshot camera before comparing.
C. Whether the flame shader was stripped from the build: URP draws stripped keyword variants white, so add it to the Always Included Shaders list.
D. Whether the flames cycle colour: they flash white during part of a 90 ms cycle, so one frame can catch them; widen the shot or take several.
E. Whether mipmap streaming had finished: streamed textures stay white until they are loaded, so wait for streaming to complete before taking the shot.
