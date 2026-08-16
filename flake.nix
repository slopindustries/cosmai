{
  description = "CosmaSignal optional development shell. The supported setup path is uv.";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          name = "cosma-signal";

          # Nix supplies non-Python system runtimes. uv owns the Python interpreter
          # and every Python package, in this shell exactly as outside it, so the two
          # paths resolve to the same environment instead of two similar ones.
          #
          # Do not add python, ruff, mypy, or pytest here. Pinning an interpreter with
          # UV_PYTHON was measured to recreate .venv on every switch between paths.
          #
          # Node and PostgreSQL ship ahead of their project files: M1 does not need
          # them, but providing the binaries now costs nothing at P0 entry.
          packages = [
            pkgs.uv
            pkgs.nodejs
            pkgs.postgresql
            pkgs.git
          ];

          shellHook = ''
            echo "cosma-signal: optional Nix shell. Nothing in this repository requires it; see README.md."
          '';
        };
      });
    };
}
