# Asset attribution

`heart.glb` and `heart.usdz` are derived from **BodyParts3D**:

> BodyParts3D, © The Database Center for Life Science, licensed under CC Attribution 4.0 International.
> https://dbarchive.biosciencedbc.jp/en/bodyparts3d/ (release 4.0, PART-OF tree, 99% reduced OBJ)

The license page states CC BY 4.0. The headers inside the source OBJ files still carry the
older CC BY-SA 2.1 Japan notice, so treat derived meshes as share-alike to be safe.
Show this attribution in the app (for example an "About / credits" screen).

Changes made: selected parts merged into named nodes (`mesh_name` in ../structures.yaml),
converted mm → m and Z-up → Y-up (+Z = anterior), recentred, recoloured, degenerate faces removed.
Rebuild with `content/_tools/build_glb.py` and `glb_to_usdz.py`.
