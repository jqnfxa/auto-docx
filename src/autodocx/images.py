"""Embed inline images into the docx body."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image as PILImage

from autodocx.ns import PIC, WP, A, R, w_tag
from autodocx.runs import make_paragraph, make_run

if TYPE_CHECKING:
    import os

# Default text-area width (165mm) and a reasonable upper bound on height.
DEFAULT_MAX_WIDTH_EMU = 5_940_000
DEFAULT_MAX_HEIGHT_EMU = 7_200_000


@dataclass
class ImageEntry:
    rid: str
    media_name: str
    abs_path: Path


@dataclass
class ImageRegistry:
    """Track images referenced by the document.

    Each unique absolute path gets a rId and a media filename (image{N}.ext)
    so we can emit relationships and copy the bytes into word/media/.
    """

    _entries: dict[Path, ImageEntry] = field(default_factory=dict)
    _next_id: int = 100  # start away from template's existing rIds

    def register(self, img_path: str | os.PathLike[str]) -> ImageEntry:
        abs_path = Path(img_path).resolve()
        if abs_path in self._entries:
            return self._entries[abs_path]
        self._next_id += 1
        ext = abs_path.suffix
        entry = ImageEntry(
            rid=f"rId{self._next_id}",
            media_name=f"image{self._next_id}{ext}",
            abs_path=abs_path,
        )
        self._entries[abs_path] = entry
        return entry

    def items(self) -> list[ImageEntry]:
        return list(self._entries.values())


def _scaled_extent(img_path: Path, max_w: int, max_h: int) -> tuple[int, int]:
    with PILImage.open(img_path) as img:
        w_px, h_px = img.size
    aspect = h_px / w_px
    cx = max_w
    cy = int(cx * aspect)
    if cy > max_h:
        cy = max_h
        cx = int(cy / aspect)
    return cx, cy


def make_image_paragraph(
    img_path: str | os.PathLike[str],
    registry: ImageRegistry,
    *,
    max_width_emu: int = DEFAULT_MAX_WIDTH_EMU,
    max_height_emu: int = DEFAULT_MAX_HEIGHT_EMU,
    fallback_caption_style: str = "Style15",
) -> ET.Element:
    """Build a centered paragraph containing an inline image.

    Falls back to a "[file not found]" caption paragraph if the image
    is missing — the build keeps going so the user can spot the gap.
    """
    path = Path(img_path)
    if not path.exists():
        print(f"  WARNING: Image not found: {path}")
        return make_paragraph(
            fallback_caption_style,
            [make_run(f"[image not found: {path.name}]")],
        )

    entry = registry.register(path)
    cx, cy = _scaled_extent(path, max_width_emu, max_height_emu)

    p = ET.Element(w_tag("p"))
    ppr = ET.SubElement(p, w_tag("pPr"))
    ET.SubElement(ppr, w_tag("jc")).set(w_tag("val"), "center")

    r = ET.SubElement(p, w_tag("r"))
    drawing = ET.SubElement(r, w_tag("drawing"))

    inline = ET.SubElement(drawing, f"{{{WP}}}inline")
    for attr in ("distT", "distB", "distL", "distR"):
        inline.set(attr, "0")

    extent = ET.SubElement(inline, f"{{{WP}}}extent")
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))

    doc_pr = ET.SubElement(inline, f"{{{WP}}}docPr")
    doc_pr.set("id", entry.rid.removeprefix("rId"))
    doc_pr.set("name", entry.media_name)

    graphic = ET.SubElement(inline, f"{{{A}}}graphic")
    graphic_data = ET.SubElement(graphic, f"{{{A}}}graphicData")
    graphic_data.set("uri", PIC)

    pic = ET.SubElement(graphic_data, f"{{{PIC}}}pic")
    nv = ET.SubElement(pic, f"{{{PIC}}}nvPicPr")
    cnv = ET.SubElement(nv, f"{{{PIC}}}cNvPr")
    cnv.set("id", entry.rid.removeprefix("rId"))
    cnv.set("name", entry.media_name)
    ET.SubElement(nv, f"{{{PIC}}}cNvPicPr")

    blip_fill = ET.SubElement(pic, f"{{{PIC}}}blipFill")
    blip = ET.SubElement(blip_fill, f"{{{A}}}blip")
    blip.set(f"{{{R}}}embed", entry.rid)
    stretch = ET.SubElement(blip_fill, f"{{{A}}}stretch")
    ET.SubElement(stretch, f"{{{A}}}fillRect")

    sp_pr = ET.SubElement(pic, f"{{{PIC}}}spPr")
    xfrm = ET.SubElement(sp_pr, f"{{{A}}}xfrm")
    off = ET.SubElement(xfrm, f"{{{A}}}off")
    off.set("x", "0")
    off.set("y", "0")
    ext = ET.SubElement(xfrm, f"{{{A}}}ext")
    ext.set("cx", str(cx))
    ext.set("cy", str(cy))
    ET.SubElement(sp_pr, f"{{{A}}}prstGeom").set("prst", "rect")

    return p
