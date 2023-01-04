# MS3DASCII Blender AddOn

Python add-on for exporting (and maybe eventually importing) MilkShape3D ASCII files for Blender.

## How to Install

1. Download the .py file(s)  
2. Open Blender, go to Edit -> Preferences -> Add-ons  
3. Click the Install button, select the .py file(s) you just downloaded, press Install  
4. Enable the add-on(s) in the same Add-ons menu

After installation, a new MS3DASCII option should be added to File -> Export

## Features

* Export all objects in a scene, or only selected objects  
* Export meshes with materials and UV maps  
* Export normals per face for flat faces, or per vertex for smoother meshes  
* Export bones and animations

## Options

* **Export Selected** - export only the selected meshes/armatures (default True)  
* **Export Animation** - export any animations defined through armatures in the objects to export (default True, no animation will be exported if no armatures are selected for export)  
* **Bone Weight Threshold** - minimum threshold for a vertex to be considered part of a bone group (default 0.5)  
* **Keyframes Per Second** - number of samples per second when exporting animation data (default 30, for best results keep this at 30 and set your render fps to a multiple of 30 in Blender!)  
* **Normals** - whether to export normals as per-face or per-vertex (default Per Face)  
* **Separate Materials** - save all materials to a separate file (default False, file will be named "\* mats.txt")  
* **Separate Animations** - save all animations to separate files (default False, only 1 animation can be saved per file, so exporting two animations with this option set to False will create one new file anyways, files will be named "\* anim X.txt" where X is an integer)
