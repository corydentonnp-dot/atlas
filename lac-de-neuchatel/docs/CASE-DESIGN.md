# Case design — style reference and fit check

The carved maple panel is an **insert**: it drops into a cherry case and the
chain grooves hold the necklace. The case is a container, not a frame.

Nothing here is cut yet. This is the dimensional groundwork.

## Style, from the references

`docs/reference/` — three saved examples.

| | |
|---|---|
| `01-helgeson-tray.png` | shallow tray, thin walls, velvet field, separate lid |
| `02-mikutowski-small-box.png` | contrasting figured lid on a darker body, low profile, softened edges |
| `03-mikutowski-pen-box.png` | same language, long and lean, rounded ends |

The shared vocabulary worth keeping:

- **Contrasting species top to bottom** — figured maple lid over a darker body.
  This already matches the panel, which is a two-species laminate glued at the
  lake datum: terrain species above Z0, lakebed species below.
- **Low and wide.** The lid is a solid slab, not a frame-and-panel.
- **Softened outer edges**, sharp inner ones. A small roundover or chamfer on
  the outside; the cavity stays crisp.
- **The contents sit fully below the rim** so the lid closes onto wood.

## Fit check against the build sheet

Case 135 × 76 × 18.5 closed, panel 122.3 × 63.0.

```
wall thickness X   (135.0 - 122.34) / 2  =  6.33 mm      1/4" is 6.35
wall thickness Y   (76.0  -  63.00) / 2  =  6.50 mm
```

Those walls are 1/4" to within a hair, which looks deliberate rather than
lucky. The panel footprint and the case size agree.

### The panel is 9.40 mm thick, not 11.0

The build sheet says the finished panel is 11.0 mm. The CAM says otherwise:

```
blank 12.0 thick, model base at lake Z -6.00  ->  stock top at lake Z +6.00
Face cuts down to lake Z +3.40, removing 2.60 mm
finished panel  =  3.40 - (-6.00)  =  9.40 mm
terrain peak sits 0.22 mm below that faced rim
```

**A 1.60 mm discrepancy.** The 12 mm blank and the 3.4 mm face height cannot
produce an 11.0 mm panel — there isn't the material. Verify before sizing the
cavity: cut it for 11.0 and the panel rattles by a millimetre and a half.

This is good news for the case, though — it buys 1.6 mm of height back.

### Height budget

Panel on the floor, walls standing 0.30 mm proud so the lid lands on wood
rather than on the carving:

| lid slab | floor |
|---|---|
| 5.0 | 3.80 |
| **5.5** | **3.30** |
| 6.0 | 2.80 |
| 6.5 | 2.30 — floor getting thin |

5.5 / 3.3 is the comfortable middle. With the lid closed flush:

```
deepest lake bed below the rim   6.40 mm
chain groove below the rim       3.90 mm
```

A pendant lying in the basin has room to spare, and the chain never touches
the lid. The whole necklace is recessed.

## The one real tension: proportion

The references — the pen box especially — are much longer and leaner than this
case will be.

```
panel      1.94 : 1     fixed by the map, cannot be changed
case spec  1.78 : 1     uniform walls make the case squatter than the panel
```

Uniform walls always squat a rectangle, because the same thickness is a larger
fraction of the short side. Two levers:

**Thin the Y walls** — runs out quickly:

| target | case | Y wall |
|---|---|---|
| 1.80 : 1 | 135.0 × 75.0 | 6.01 |
| 1.90 : 1 | 135.0 × 71.1 | 4.04 |
| 2.00 : 1 | 135.0 × 67.5 | 2.26 — too thin to hinge into |

**Add length at the ends** — holds Y walls at 6.35 and grows X:

| target | case | X wall |
|---|---|---|
| 1.80 : 1 | 136.3 × 75.7 | 7.0 |
| 1.94 : 1 | 146.9 × 75.7 | 12.3 |
| 2.10 : 1 | 159.0 × 75.7 | 18.3 |
| 2.50 : 1 | 189.2 × 75.7 | 33.5 |

Note the middle row: **12.3 mm end walls make the case echo the panel's own
1.94 : 1**, which is a defensible proportion to land on — the box repeats the
shape of the map inside it. Wider end blocks are also somewhere to put a
hinge, a catch, or an inlay.

Past about 2.1 : 1 the ends become blocks rather than walls, and it stops
reading as a jewellery box.

**The pen-box look is not reachable with this map.** That box is roughly 4 : 1;
Lac de Neuchâtel is 1.94 : 1. The case will read closer to
`02-mikutowski-small-box.png` — which is arguably the better reference anyway,
since it is the one holding jewellery.

## Open questions

1. **Panel thickness** — is 11.0 mm the intent (then the blank or the face
   height has to change), or is 9.40 mm fine (then the build sheet needs
   correcting)?
2. **Proportion** — stay at the specified 135 × 76, or stretch the ends to
   146.9 × 75.7 so the case matches the panel's own ratio?
3. **Hinge** — the references use small barrel or knife hinges. Barrel hinges
   want wall thickness; at 6.35 mm they will be tight.
4. **Retention** — does the panel sit loose in the cavity, or get seated on
   felt or a rebate?

None of this blocks the carving. The panel can be cut before the case exists.
