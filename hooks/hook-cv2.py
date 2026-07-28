# Override: skip recursive submodule collection to avoid OpenBLAS crash.
# cv2 is optional (video_background.py fallback), import only the top level.
hiddenimports = ['cv2']
