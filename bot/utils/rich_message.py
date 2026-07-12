"""Shared rendering helper for the dashboard embed builders.

The dashboard stores each designed message as one JSON blob (the `*_embed`
columns). That blob now carries a `format` discriminator:

  format == 'embed'         → a classic discord.Embed (unchanged behaviour)
  format == 'components_v2' → a Discord Components V2 message: an accent-
                              coloured Container holding ordered content
                              blocks (text / separator / image).

`build_layout_view()` turns the V2 config into a `discord.ui.LayoutView`.
Cogs decide per message: if `is_components_v2(cfg)` → send/edit with
`view=...` (NO content/embed — Discord forbids mixing them with a V2 view),
otherwise build a classic embed as before.

The block/URL text is resolved through caller-supplied callables so each cog
keeps its own placeholder vocabulary ({user}/{guild}, {creator}/{platform},
{status}/{players}, …).
"""

import discord

DEFAULT_ACCENT = 0x5865F2
_V2_TEXT_CAP = 4000


def is_components_v2(cfg):
    """True when this embed config should render as a Components V2 message."""
    return bool(cfg) and isinstance(cfg, dict) and cfg.get("format") == "components_v2"


def _parse_color(color_str, fallback=DEFAULT_ACCENT):
    """'#RRGGBB' → discord.Colour; anything invalid → fallback."""
    try:
        if isinstance(color_str, str) and color_str.startswith("#") and len(color_str) == 7:
            return discord.Colour(int(color_str[1:], 16))
    except (ValueError, TypeError):
        pass
    return discord.Colour(fallback)


def _add_action_items(container, items):
    """Group interactive items (Buttons / Select) into ActionRows inside the
    container: buttons chunk 5 per row, a select gets its own row."""
    if not items:
        return False
    added = False
    buf = []

    def flush():
        if buf:
            row = discord.ui.ActionRow()
            for it in buf:
                row.add_item(it)
            container.add_item(row)
            buf.clear()

    for it in items:
        if isinstance(it, discord.ui.Button):
            buf.append(it)
            added = True
            if len(buf) == 5:
                flush()
        else:
            # Select (or any non-button component) must be alone in its row.
            flush()
            row = discord.ui.ActionRow()
            row.add_item(it)
            container.add_item(row)
            added = True
    flush()
    return added


def build_layout_view(cfg, resolve_text=None, resolve_url=None, extra_top=None, action_items=None):
    """Build a discord.ui.LayoutView from a Components V2 config.

    Args:
        cfg: the parsed embed config dict (with `accent_color` + `blocks`).
        resolve_text: callable(str) -> str applied to every text block
            (placeholder substitution). Defaults to identity.
        resolve_url: callable(str) -> str applied to every image URL
            (e.g. to resolve `{user.avatar}`). Defaults to identity.
            Return a falsy value to drop the image.
        extra_top: optional already-resolved string added as the first text
            block (used for a ping mention / [TEST] marker).
        action_items: optional list of discord.ui Buttons / a Select to append
            inside the container as ActionRow(s). These count as content, so an
            interactive panel with no text blocks still renders.

    Returns:
        A LayoutView, or None if there is no renderable content (so the caller
        can fall back to a plain message / classic embed).
    """
    if not cfg or not isinstance(cfg, dict):
        return None

    rt = resolve_text or (lambda s: s)
    ru = resolve_url or (lambda s: s)

    accent = _parse_color(cfg.get("accent_color") or cfg.get("color"))
    container = discord.ui.Container(accent_colour=accent)
    has_content = False

    if extra_top:
        container.add_item(discord.ui.TextDisplay(str(extra_top)[:_V2_TEXT_CAP]))
        has_content = True

    for block in cfg.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            content = rt(block.get("content") or "")
            if content and str(content).strip():
                container.add_item(discord.ui.TextDisplay(str(content)[:_V2_TEXT_CAP]))
                has_content = True
        elif btype == "separator":
            spacing = (
                discord.SeparatorSpacing.large
                if block.get("spacing") == 2
                else discord.SeparatorSpacing.small
            )
            container.add_item(
                discord.ui.Separator(visible=block.get("divider") is not False, spacing=spacing)
            )
        elif btype == "image":
            url = ru(block.get("url") or "")
            if url:
                try:
                    container.add_item(
                        discord.ui.MediaGallery(discord.MediaGalleryItem(str(url)))
                    )
                    has_content = True
                except Exception as exc:  # invalid media url — skip, don't crash
                    print(f"[rich_message] media item failed: {exc}")

    if _add_action_items(container, action_items):
        has_content = True

    if not has_content:
        return None

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
