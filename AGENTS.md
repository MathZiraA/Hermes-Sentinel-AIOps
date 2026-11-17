<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

## What Lovable manages

Rules outside this block are the project's own. Change the pieces below in
Lovable, not by hand. With the [Lovable MCP](https://mcp.lovable.dev)
connected, `send_message` asks Lovable to do it; otherwise ask the user to
use the editor.

- **Database.** Do not add or edit `supabase/migrations/` or `drizzle/`.
  Ask Lovable to change the schema.
- **Generated files.** Do not edit a file whose header says it is automatically
  generated.
- **AI gateway.** Keep model calls on Lovable's gateway, and keep
  `LOVABLE_API_KEY` out of browser code.
- **Connectors.** Lovable provides native connectors. `list_connectors` shows
  which are enabled; `add_connector` only returns the dashboard link. When a
  connector is enabled, calls go through the connector gateway and need
  `LOVABLE_API_KEY`. When Lovable does not provide one, users can bring their
  own key and store it in Secrets.
- **Secrets.** Lovable manages them. Do not put secret values in the repo.
<!-- LOVABLE:END -->

<!-- AGENT-MEMORY:BEGIN -->
- Isometric office is pure CSS 3D: `src/components/office/iso.tsx` (IsoBox/Decal/Billboard in floor-space px, `project()` for 2D overlays). Why: keeps 3D depth sorting in the browser; never put a non-preserve-3d wrapper (plain div, filter, overflow) between the world and its objects or they flatten.
- Speech bubbles render in a 2D overlay positioned with `project()`, not as 3D billboards. Why: always on top and never clipped by furniture.
<!-- AGENT-MEMORY:END -->

<!-- AGENT-MEMORY:BEGIN -->
- Isometric office is pure CSS 3D: `src/components/office/iso.tsx` (IsoBox/Decal/Billboard in floor-space px, `project()` for 2D overlays). Why: browser handles depth sorting; never put a plain div, filter or overflow wrapper between the world and its objects or they flatten.
- Speech bubbles render in a 2D overlay positioned with `project()`, not as 3D billboards. Why: always on top and never clipped by furniture.
<!-- AGENT-MEMORY:END -->
