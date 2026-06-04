import pygetwindow as gw

for w in gw.getAllWindows():
    if w.title.strip():
        print(f"title={w.title!r} | left={w.left} top={w.top} width={w.width} height={w.height}")
