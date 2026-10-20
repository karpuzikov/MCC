"""MCC compact dark Flet UI test bench. Read-only demo, no audio processing."""
import flet as ft

def main(page: ft.Page):
    page.title = "MCC - Flet Compact Bench"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#10151d"
    page.padding = 12
    page.spacing = 8
    page.window.width = 1180
    page.window.height = 740
    page.window.min_width = 850
    page.window.min_height = 540
    status = ft.Text("Ready  •  Demo data  •  No audio scanned", size=12, color="#9aa8ba")
    def demo(message):
        status.value = message + " - demo only"
        page.update()
    def action(name):
        return lambda e: demo(name)
    def button(name, filled=False):
        cls = ft.FilledButton if filled else ft.OutlinedButton
        return cls(name, on_click=action(name))
    header = ft.Row([
        ft.Text("Music Collection Cleaner  /  UI Bench", size=17, weight=ft.FontWeight.BOLD),
        ft.Container(expand=True),
        ft.Text("Flet  •  Dark", size=12, color="#9aa8ba")
    ])
    paths = ft.Row([
        ft.TextField(label="OLD", value=r"D:\\Music\\Existing", dense=True, expand=True),
        ft.TextField(label="NEW", value=r"D:\\Music\\Incoming", dense=True, expand=True),
    ], spacing=8)
    controls = ft.Row([
        ft.Text("Save Remixes", size=12), ft.Switch(value=False, scale=0.75),
        ft.Text("Save Live", size=12), ft.Switch(value=False, scale=0.75),
        ft.Container(expand=True), button("Analyze", True),
    ], spacing=6)
    releases = [
        ("808s & Heartbreak [602557134230]", ["Pinocchio Story", "Heartless", "Love Lockdown"]),
        ("808s & Heartbreak [JP - UICD-9058]", ["Pinocchio Story (Freestyle Live from Singapore)", "Heartless"]),
        ("Discovery [CD]", ["One More Time", "Digital Love"]),
    ]
    release_rows = []
    for name, tracks in releases:
        release_rows.append(ft.ExpansionTile(
            title=ft.Text(name, size=13),
            subtitle=ft.Text(f"{len(tracks)} tracks  •  Review", size=11),
            initially_expanded=True,
            controls=[ft.ListTile(
                dense=True,
                title=ft.Text(t, size=12),
                trailing=ft.Text("Acoustic match" if "Pinocchio" in t else "Included", size=11),
                on_click=action("Selected " + t),
            ) for t in tracks],
        ))
    left = ft.Container(
        content=ft.Column([
            ft.Row([ft.Text("Releases", weight=ft.FontWeight.BOLD), ft.Container(expand=True), ft.Text("3 demo releases", size=11)]),
            ft.Divider(height=1),
            ft.Column(release_rows, scroll=ft.ScrollMode.AUTO, spacing=0, expand=True),
        ], expand=True, spacing=5),
        padding=10, bgcolor="#1b2532", border_radius=7, expand=7,
    )
    right = ft.Container(
        content=ft.Column([
            ft.Text("Release details", size=15, weight=ft.FontWeight.BOLD),
            ft.Text("808s & Heartbreak - Japanese edition", size=12),
            ft.Text("2 tracks  •  1 matching recording  •  Demo", size=11, color="#9aa8ba"),
            ft.Divider(height=1),
            ft.Text("Acoustic evidence is authoritative.", size=12),
            ft.Text("Live labels affect retention, not identity.", size=12),
            ft.Container(expand=True),
            ft.Row([button("Keep"), button("Ignore"), button("Compare")], wrap=True),
        ], expand=True, spacing=8),
        padding=12, bgcolor="#1b2532", border_radius=7, expand=3,
    )
    workspace = ft.Row([left, right], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    footer = ft.Row([
        ft.Text("Selected: 0  •  Excluded: 0  •  Changes: 0", size=11),
        ft.Container(expand=True), button("Copy OLD + NEW"), button("Move OLD + NEW"),
    ], spacing=8)
    page.add(header, paths, controls, status, workspace, footer)

if __name__ == "__main__":
    ft.app(target=main)
