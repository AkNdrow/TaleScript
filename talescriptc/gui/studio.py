"""
TaleScript Studio — IDE Gráfico y Visualizador de la Máquina de Estados
========================================================================
Entorno de desarrollo visual para TaleScript implementado exclusivamente
con Tkinter estándar (cero dependencias externas).

Incluye:
  - Editor de código con resaltado de sintaxis y números de línea.
  - Visualizador de Máquina de Estados (EFSM): Grafo interactivo de nodos y transiciones.
  - Pestañas de inspección técnica: Tokens, Símbolos, TAC, Optimizador, ASM y Consola.
  - Compilación a cuádruplas y generación de ejecutables .exe con 1 clic.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Any

from talescriptc.lexer.lexer import crear_lexer, tokens, reserved
from talescriptc.parser.parser import parsear, ResultadoCompilacion
from talescriptc.intermedio.cuadrupla import dump_cuadruplas, dump_tripletas, cuadruplas_a_tripletas
from talescriptc.optimizador.optimizador import Optimizador
from talescriptc.backend.generador_x86_64 import GeneradorX86_64
from talescriptc.semantica.formato_errores import (
    segmentos_error, TITULO_ERROR, TITULO_AVISO, UBICACION, MARGEN, CODIGO,
    MARCA_ERROR, MARCA_AVISO, AYUDA, NORMAL,
)
from talescriptc.semantica.gestor_errores import ERROR as SEVERIDAD_ERROR
from talescriptc.semantica.formato_errores import _columna_y_longitud


# ---------------------------------------------------------------------------
# Paleta de Colores (Tema Oscuro Moderno - Catppuccin / VS Code Dark)
# ---------------------------------------------------------------------------
BG_DARK = "#181825"        # Fondo principal oscuro
BG_EDITOR = "#1e1e2e"      # Fondo del editor y terminales
BG_PANEL = "#252538"       # Fondo de tarjetas y paneles laterales
BG_TOOLBAR = "#181825"     # Fondo de barra de herramientas
BORDER_COLOR = "#313244"   # Bordes sutiles

TEXT_COLOR = "#cdd6f4"     # Texto blanco suave
TEXT_MUTED = "#6c7086"     # Comentarios / texto secundario

ACCENT_BLUE = "#89b4fa"    # Azul primario (palabras clave)
ACCENT_GREEN = "#a6e3a1"   # Verde (éxito, tipos, cadenas)
ACCENT_YELLOW = "#f9e2af"  # Amarillo (advertencias, opciones)
ACCENT_RED = "#f38ba8"     # Rojo (errores, números)
ACCENT_PURPLE = "#cba6f7"  # Púrpura (nodos, control)
ACCENT_CYAN = "#89dceb"    # Cian (operadores, directivas)


class LineNumbers(tk.Canvas):
    """Gutter con números de línea para el editor de código."""
    def __init__(self, parent, text_widget, **kwargs):
        super().__init__(parent, **kwargs)
        self.text_widget = text_widget
        self.config(bg=BG_TOOLBAR, bd=0, highlightthickness=0, width=42)
        self.lineas_error: set = set()

    def redraw(self):
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            con_error = int(linenum) in self.lineas_error
            if con_error:
                self.create_text(8, y + 2, anchor="nw", text="●", fill=ACCENT_RED, font=("Consolas", 9))
            self.create_text(
                36, y + 2, anchor="ne", text=linenum,
                fill=ACCENT_RED if con_error else TEXT_MUTED,
                font=("Consolas", 10, "bold") if con_error else ("Consolas", 10)
            )
            i = self.text_widget.index(f"{i}+1line")


class CodeEditor(tk.Frame):
    """Editor de código con resaltado de sintaxis en tiempo real."""
    def __init__(self, parent, on_change_callback=None, **kwargs):
        super().__init__(parent, bg=BG_EDITOR, bd=0, highlightthickness=0, **kwargs)
        self.on_change_callback = on_change_callback

        self.text = tk.Text(
            self, bg=BG_EDITOR, fg=TEXT_COLOR, insertbackground=ACCENT_BLUE,
            selectbackground="#45475a", selectforeground=TEXT_COLOR,
            wrap="none", font=("Consolas", 11), undo=True,
            bd=0, padx=6, pady=4, highlightthickness=0
        )
        self.line_numbers = LineNumbers(self, self.text)

        self.scroll_y = ttk.Scrollbar(self, orient="vertical", command=self._scroll_both_y)
        self.scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._on_text_scroll_y, xscrollcommand=self.scroll_x.set)

        self.line_numbers.pack(side="left", fill="y")
        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.text.pack(side="left", fill="both", expand=True)

        self._configure_syntax_tags()
        self.text.bind("<KeyRelease>", self._on_key_release)
        self.text.bind("<MouseWheel>", lambda e: self.after_idle(self.line_numbers.redraw))

    def _scroll_both_y(self, *args):
        self.text.yview(*args)
        self.line_numbers.redraw()

    def _on_text_scroll_y(self, first, last):
        self.scroll_y.set(first, last)
        self.line_numbers.redraw()

    def _configure_syntax_tags(self):
        self.text.tag_configure("keyword", foreground=ACCENT_PURPLE, font=("Consolas", 11, "bold"))
        self.text.tag_configure("type", foreground=ACCENT_CYAN, font=("Consolas", 11, "bold"))
        self.text.tag_configure("string", foreground=ACCENT_GREEN)
        self.text.tag_configure("interp", foreground=ACCENT_YELLOW, font=("Consolas", 11, "bold"))
        self.text.tag_configure("number", foreground=ACCENT_RED)
        self.text.tag_configure("comment", foreground=TEXT_MUTED, font=("Consolas", 11, "italic"))
        self.text.tag_configure("node_name", foreground=ACCENT_BLUE, font=("Consolas", 11, "bold"))
        # Marcas de diagnóstico (fondo de línea y subrayado del punto exacto)
        self.text.tag_configure("error_line", background="#3a2232")
        self.text.tag_configure("warning_line", background="#3a3428")
        self.text.tag_configure("error_mark", background="#7a2e45", underline=True)
        self.text.tag_configure("warning_mark", background="#6b5a32", underline=True)
        self.text.tag_configure("goto_line", background="#2b4365")
        self.text.tag_raise("sel")

    def highlight_syntax(self):
        content = self.text.get("1.0", "end-1c")
        for tag in ("keyword", "type", "string", "interp", "number", "comment", "node_name"):
            self.text.tag_remove(tag, "1.0", "end")

        # Comentarios //
        for m in re.finditer(r"//[^\n]*", content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.text.tag_add("comment", start, end)

        # Cadenas y su interpolación
        for m in re.finditer(r'"([^"\\]|\\.)*"', content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.text.tag_add("string", start, end)
            s_text = m.group(0)
            for im in re.finditer(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", s_text):
                istart = f"1.0+{m.start() + im.start()}c"
                iend = f"1.0+{m.start() + im.end()}c"
                self.text.tag_add("interp", istart, iend)

        # Palabras clave
        kw_pattern = r"\b(node|choice|say|goto|call|return|if|else|while|do|end|and|or|not|true|false|global|local|const)\b"
        for m in re.finditer(kw_pattern, content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.text.tag_add("keyword", start, end)

        # Tipos
        type_pattern = r"\b(int|string|bool)\b"
        for m in re.finditer(type_pattern, content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.text.tag_add("type", start, end)

        # Números
        for m in re.finditer(r"\b\d+\b", content):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.text.tag_add("number", start, end)

        # Nombres de nodos tras 'node'
        for m in re.finditer(r"\bnode\s+([a-zA-Z_][a-zA-Z0-9_]*)", content):
            start = f"1.0+{m.start(1)}c"
            end = f"1.0+{m.end(1)}c"
            self.text.tag_add("node_name", start, end)

    def _on_key_release(self, event=None):
        if event is not None and event.char:
            self.limpiar_errores()
        self.line_numbers.redraw()
        self.highlight_syntax()
        if self.on_change_callback:
            self.on_change_callback()

    def get_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    def limpiar_errores(self):
        for tag in ("error_line", "warning_line", "error_mark", "warning_mark", "goto_line"):
            self.text.tag_remove(tag, "1.0", "end")
        self.line_numbers.lineas_error = set()
        self.line_numbers.redraw()

    def marcar_errores(self, registros):
        """Resalta en el editor cada línea con diagnóstico y subraya la columna exacta."""
        self.limpiar_errores()
        total = int(self.text.index("end-1c").split(".")[0])
        lineas_error = set()
        for reg in registros:
            if not (1 <= reg.linea <= total):
                continue
            es_error = reg.severidad == SEVERIDAD_ERROR
            linea_tag = "error_line" if es_error else "warning_line"
            marca_tag = "error_mark" if es_error else "warning_mark"
            self.text.tag_add(linea_tag, f"{reg.linea}.0", f"{reg.linea}.0 lineend")
            texto = self.text.get(f"{reg.linea}.0", f"{reg.linea}.0 lineend")
            col, largo = _columna_y_longitud(reg, texto)
            inicio = f"{reg.linea}.{col - 1}"
            self.text.tag_add(marca_tag, inicio, f"{inicio}+{largo}c")
            if es_error:
                lineas_error.add(reg.linea)
        self.line_numbers.lineas_error = lineas_error
        self.line_numbers.redraw()

    def ir_a_linea(self, linea: int):
        """Lleva el cursor a la línea indicada y la destaca brevemente."""
        self.text.see(f"{linea}.0")
        self.text.mark_set("insert", f"{linea}.0")
        self.text.tag_remove("goto_line", "1.0", "end")
        self.text.tag_add("goto_line", f"{linea}.0", f"{linea}.0 lineend+1c")
        self.text.focus_set()
        self.after(900, lambda: self.text.tag_remove("goto_line", "1.0", "end"))
        self.line_numbers.redraw()

    def set_text(self, content: str):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.line_numbers.redraw()
        self.highlight_syntax()


class StateMachineCanvas(tk.Frame):
    """Visualizador gráfico interactivo de la Máquina de Estados Finitos (EFSM)."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_EDITOR, **kwargs)
        self.canvas = tk.Canvas(self, bg=BG_EDITOR, bd=0, highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)

        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)

        self.node_positions: dict[str, tuple[int, int]] = {}
        self.node_items: dict[str, list[int]] = {}
        self._dragging_node = None
        self._drag_start = (0, 0)

        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)

    def update_graph(self, resultado: ResultadoCompilacion):
        self.canvas.delete("all")
        self.node_positions.clear()
        self.node_items.clear()

        # Extraer nodos y transiciones del código TAC
        nodes: list[str] = []
        transitions: list[tuple[str, str, str]] = []  # (origen, destino, etiqueta)
        nodo_actual = None

        for cuad in resultado.codigo_tac:
            if cuad.op == "node":
                nodo_actual = cuad.res
                if nodo_actual not in nodes:
                    nodes.append(nodo_actual)
            elif nodo_actual:
                if cuad.op in ("goto", "call"):
                    destino = cuad.res
                    if destino in resultado.tabla_simbolos.tabla_nodes:
                        transitions.append((nodo_actual, destino, cuad.op))
                elif cuad.op == "opt":
                    # (opt, "Texto", -, Lk)
                    texto_opt = cuad.arg1.strip('"')
                    transitions.append((nodo_actual, f"_choice_{cuad.res}", texto_opt))

        # Disposición automática (Layout jerárquico por columnas y niveles)
        if not nodes:
            self.canvas.create_text(
                200, 150, text="Escribe o carga un programa TaleScript para visualizar el grafo de estados.",
                fill=TEXT_MUTED, font=("Consolas", 11)
            )
            return

        spacing_x = 220
        spacing_y = 120
        start_x = 60
        start_y = 50

        for idx, node in enumerate(nodes):
            col = idx % 3
            row = idx // 3
            x = start_x + col * spacing_x
            y = start_y + row * spacing_y
            self.node_positions[node] = (x, y)

        # 1. Dibujar transiciones (Flechas)
        for orig, dest, label in transitions:
            if orig in self.node_positions and dest in self.node_positions:
                x1, y1 = self.node_positions[orig]
                x2, y2 = self.node_positions[dest]
                # Conectar desde el centro de las tarjetas
                cx1, cy1 = x1 + 75, y1 + 35
                cx2, cy2 = x2 + 75, y2 + 35

                color_flecha = ACCENT_PURPLE if label == "call" else ACCENT_CYAN
                if orig == dest:
                    # Bucle sobre sí mismo
                    self.canvas.create_arc(
                        cx1 - 30, cy1 - 50, cx1 + 30, cy1, start=0, extent=180,
                        style="arc", outline=color_flecha, width=2
                    )
                else:
                    self.canvas.create_line(
                        cx1, cy1, cx2, cy2, arrow=tk.LAST, fill=color_flecha,
                        width=2, smooth=True, arrowshape=(10, 12, 5)
                    )
                    # Etiqueta en el punto medio
                    mx = (cx1 + cx2) // 2
                    my = (cy1 + cy2) // 2
                    self.canvas.create_text(
                        mx, my - 8, text=label, fill=ACCENT_YELLOW,
                        font=("Consolas", 9, "bold")
                    )

        # 2. Dibujar nodos (Tarjetas de estado)
        for node, (x, y) in self.node_positions.items():
            w, h = 150, 70
            is_entry = (node == "inicio" or (resultado.tabla_simbolos.tabla_nodes.get(node) and
                                             getattr(resultado.tabla_simbolos.tabla_nodes[node], "orden", -1) == 0))

            outline = ACCENT_GREEN if is_entry else ACCENT_BLUE
            fill_header = "#2d3548" if is_entry else "#2b2d42"

            # Tarjeta de fondo
            r_box = self.canvas.create_rectangle(
                x, y, x + w, y + h, fill=BG_PANEL, outline=outline, width=2, tags=node
            )
            r_header = self.canvas.create_rectangle(
                x, y, x + w, y + 24, fill=fill_header, outline="", tags=node
            )

            # Textos
            badge = "[INICIO]" if is_entry else "[NODE]"
            t_badge = self.canvas.create_text(
                x + 8, y + 12, text=badge, fill=ACCENT_GREEN if is_entry else ACCENT_BLUE,
                font=("Consolas", 8, "bold"), anchor="w", tags=node
            )
            t_name = self.canvas.create_text(
                x + w - 8, y + 12, text=node, fill=TEXT_COLOR,
                font=("Consolas", 10, "bold"), anchor="e", tags=node
            )

            # Información de variables locales
            nodo_info = resultado.tabla_simbolos.tabla_nodes.get(node)
            vars_str = "(sin locales)"
            if nodo_info and getattr(nodo_info, "tabla_local", None):
                vars_count = len(nodo_info.tabla_local)
                vars_str = f"Locales: {vars_count} var(s)"

            t_info = self.canvas.create_text(
                x + 8, y + 45, text=vars_str, fill=TEXT_MUTED,
                font=("Consolas", 8), anchor="w", tags=node
            )

            self.node_items[node] = [r_box, r_header, t_badge, t_name, t_info]

        self.canvas.config(scrollregion=self.canvas.bbox("all") or (0, 0, 800, 600))

    def _on_click(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        item = self.canvas.find_closest(x, y)
        if item:
            tags = self.canvas.gettags(item[0])
            for tag in tags:
                if tag in self.node_positions:
                    self._dragging_node = tag
                    self._drag_start = (x, y)
                    break

    def _on_drag(self, event):
        if not self._dragging_node:
            return
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = x - self._drag_start[0]
        dy = y - self._drag_start[1]
        self._drag_start = (x, y)

        orig_x, orig_y = self.node_positions[self._dragging_node]
        self.node_positions[self._dragging_node] = (orig_x + dx, orig_y + dy)
        for elem in self.node_items.get(self._dragging_node, []):
            self.canvas.move(elem, dx, dy)


class TaleScriptStudio(tk.Tk):
    """Ventana principal del IDE TaleScript Studio."""
    def __init__(self):
        super().__init__()
        self.title("TaleScript Studio — IDE del Compilador de Historias Interactivas")
        self.geometry("1280x800")
        self.minsize(960, 600)
        self.configure(bg=BG_DARK)

        self._current_file: Optional[str] = None
        self._resultado: Optional[ResultadoCompilacion] = None

        self._setup_styles()
        self._build_menu()
        self._build_toolbar()
        self._build_main_panels()
        self._build_status_bar()

        # Cargar un ejemplo inicial por defecto
        self._load_default_script()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TNotebook", background=BG_TOOLBAR, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_TOOLBAR, foreground=TEXT_MUTED,
                        padding=[8, 5], font=("Segoe UI", 9), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG_PANEL)],
                  foreground=[("selected", ACCENT_BLUE)])

        style.configure("TCombobox", fieldbackground=BG_EDITOR, background=BG_TOOLBAR,
                        foreground=TEXT_COLOR, arrowcolor=ACCENT_BLUE)
        # En modo 'readonly' el tema clam pinta el campo gris claro y el texto no se lee
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_EDITOR)],
                  foreground=[("readonly", TEXT_COLOR)],
                  selectbackground=[("readonly", BG_EDITOR)],
                  selectforeground=[("readonly", TEXT_COLOR)])
        style.configure("TScrollbar", background=BG_TOOLBAR, troughcolor=BG_DARK, borderwidth=0)

    def _build_menu(self):
        menubar = tk.Menu(self, bg=BG_TOOLBAR, fg=TEXT_COLOR, activebackground=ACCENT_BLUE,
                          activeforeground=BG_DARK, bd=0)
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=TEXT_COLOR)
        file_menu.add_command(label="Nuevo", accelerator="Ctrl+N", command=self._nuevo_archivo)
        file_menu.add_command(label="Abrir archivo...", accelerator="Ctrl+O", command=self._abrir_archivo)
        file_menu.add_command(label="Guardar", accelerator="Ctrl+S", command=self._guardar_archivo)
        file_menu.add_command(label="Guardar como...", command=self._guardar_como)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        # Menú Compilar
        compile_menu = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=TEXT_COLOR)
        compile_menu.add_command(label="Compilar (F5)", accelerator="F5", command=self.compilar)
        compile_menu.add_command(label="Compilar y Ejecutar (.exe)", accelerator="Ctrl+F5", command=self.compilar_y_ejecutar)
        menubar.add_cascade(label="Compilación", menu=compile_menu)

        # Menú Ejemplos
        examples_menu = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=TEXT_COLOR)
        examples_menu.add_command(label="Historia Base (historia.ts)", command=lambda: self._cargar_ejemplo("historia.ts"))
        examples_menu.add_command(label="Combate Épico Completo (combate_epico.ts)", command=lambda: self._cargar_ejemplo("combate_epico.ts"))
        examples_menu.add_command(label="Fibonacci Iterativo (fibonacci.ts)", command=lambda: self._cargar_ejemplo("fibonacci.ts"))
        examples_menu.add_command(label="Factorial (factorial.ts)", command=lambda: self._cargar_ejemplo("factorial.ts"))
        menubar.add_cascade(label="Ejemplos", menu=examples_menu)

        # Menú Errores de demostración (tests/errores_demo/*.ts)
        demo_menu = tk.Menu(menubar, tearoff=0, bg=BG_PANEL, fg=TEXT_COLOR)
        for nombre in self._listar_demos_error():
            demo_menu.add_command(
                label=nombre, command=lambda n=nombre: self._cargar_ejemplo(n, carpeta="errores_demo"))
        menubar.add_cascade(label="Errores de demostración", menu=demo_menu)

        self.config(menu=menubar)
        self.bind("<F5>", lambda e: self.compilar())
        self.bind("<Control-F5>", lambda e: self.compilar_y_ejecutar())
        self.bind("<Control-s>", lambda e: self._guardar_archivo())

    def _build_toolbar(self):
        toolbar = tk.Frame(self, bg=BG_TOOLBAR, height=44, bd=0, padx=10, pady=6)
        toolbar.pack(side="top", fill="x")

        # Botón Compilar
        btn_compile = tk.Button(
            toolbar, text="▶ Compilar (F5)", bg="#2b4365", fg=ACCENT_BLUE,
            activebackground=ACCENT_BLUE, activeforeground=BG_DARK,
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=3,
            cursor="hand2", command=self.compilar
        )
        btn_compile.pack(side="left", padx=4)

        # Botón Compilar y Ejecutar .exe
        btn_run = tk.Button(
            toolbar, text="⚡ Compilar y Ejecutar (.exe)", bg="#234e35", fg=ACCENT_GREEN,
            activebackground=ACCENT_GREEN, activeforeground=BG_DARK,
            font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=3,
            cursor="hand2", command=self.compilar_y_ejecutar
        )
        btn_run.pack(side="left", padx=4)

        # Nivel de Optimización (-O0 / -O1)
        lbl_opt = tk.Label(toolbar, text="Optimización:", bg=BG_TOOLBAR, fg=TEXT_MUTED, font=("Segoe UI", 9))
        lbl_opt.pack(side="left", padx=(16, 4))

        self.opt_var = tk.StringVar(value="-O1")
        opt_combo = ttk.Combobox(toolbar, textvariable=self.opt_var, values=["-O0", "-O1"], width=6, state="readonly")
        opt_combo.pack(side="left", padx=2)

        # Selector de Ejemplos
        lbl_ex = tk.Label(toolbar, text="Cargar Ejemplo:", bg=BG_TOOLBAR, fg=TEXT_MUTED, font=("Segoe UI", 9))
        lbl_ex.pack(side="left", padx=(16, 4))

        self.example_var = tk.StringVar(value="Seleccionar...")
        ex_combo = ttk.Combobox(
            toolbar, textvariable=self.example_var,
            values=["historia.ts", "combate_epico.ts", "fibonacci.ts", "factorial.ts"],
            width=18, state="readonly"
        )
        ex_combo.pack(side="left", padx=2)
        ex_combo.bind("<<ComboboxSelected>>", lambda e: self._cargar_ejemplo(self.example_var.get()))

        # Selector de errores de demostración
        lbl_err = tk.Label(toolbar, text="Errores demo:", bg=BG_TOOLBAR, fg=TEXT_MUTED, font=("Segoe UI", 9))
        lbl_err.pack(side="left", padx=(16, 4))
        self.demo_var = tk.StringVar(value="Seleccionar...")
        demo_combo = ttk.Combobox(
            toolbar, textvariable=self.demo_var, values=self._listar_demos_error(),
            width=30, state="readonly"
        )
        demo_combo.pack(side="left", padx=2)
        demo_combo.bind("<<ComboboxSelected>>",
                        lambda e: self._cargar_ejemplo(self.demo_var.get(), carpeta="errores_demo"))

        # Etiqueta de archivo actual a la derecha
        self.lbl_archivo = tk.Label(toolbar, text="Nuevo archivo", bg=BG_TOOLBAR, fg=TEXT_MUTED, font=("Segoe UI", 9, "italic"))
        self.lbl_archivo.pack(side="right", padx=10)

    def _build_main_panels(self):
        # Panel principal dividido horizontalmente: Izquierda = Editor, Derecha = Notebook de Inspección
        self.paned_main = tk.PanedWindow(self, orient="horizontal", bg=BORDER_COLOR, bd=1, sashwidth=4)
        self.paned_main.pack(fill="both", expand=True, padx=4, pady=4)

        # --- Lado Izquierdo: Editor de Código ---
        frame_editor = tk.Frame(self.paned_main, bg=BG_EDITOR)
        self.editor = CodeEditor(frame_editor, on_change_callback=self._on_code_modified)
        self.editor.pack(fill="both", expand=True)
        self.paned_main.add(frame_editor, minsize=400, width=540)

        # --- Lado Derecho: Notebook de Inspección y Visualización ---
        frame_tabs = tk.Frame(self.paned_main, bg=BG_DARK)
        self.notebook = ttk.Notebook(frame_tabs)
        self.notebook.pack(fill="both", expand=True)

        # 1. Pestaña: Máquina de Estados (Grafo)
        self.tab_graph = StateMachineCanvas(self.notebook)
        self.notebook.add(self.tab_graph, text=" Máquina de Estados (EFSM) ")

        # 2. Pestaña: Tokens
        self.tab_tokens = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_tokens["frame"], text=" Tokens ")

        # 3. Pestaña: Tabla de Símbolos
        self.tab_symtab = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_symtab["frame"], text=" Tabla de Símbolos ")

        # 4. Pestaña: Código Intermedio (TAC / Tripletas)
        self.tab_tac = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_tac["frame"], text=" TAC (Cuádruplas) ")

        # 5. Pestaña: Optimizador (-O1)
        self.tab_opt = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_opt["frame"], text=" Optimizador (-O1) ")

        # 6. Pestaña: Ensamblador NASM x86-64
        self.tab_asm = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_asm["frame"], text=" Ensamblador NASM ")

        # 7. Pestaña: Consola de Salida y Errores
        self.tab_console = self._crear_panel_texto(self.notebook)
        self.notebook.add(self.tab_console["frame"], text=" Consola / Errores ")
        # El reporte detallado incluye sugerencias largas: ajustar por palabras
        self.tab_console["text"].config(wrap="word")

        self.paned_main.add(frame_tabs, minsize=400, width=740)

    def _crear_panel_texto(self, parent) -> dict:
        frame = tk.Frame(parent, bg=BG_EDITOR)
        txt = tk.Text(
            frame, bg=BG_EDITOR, fg=TEXT_COLOR, font=("Consolas", 10),
            wrap="none", bd=0, padx=8, pady=6, highlightthickness=0
        )
        sy = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        sx = ttk.Scrollbar(frame, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        sy.pack(side="right", fill="y")
        sx.pack(side="bottom", fill="x")
        txt.pack(fill="both", expand=True)

        txt.tag_configure("error", foreground=ACCENT_RED, font=("Consolas", 10, "bold"))
        txt.tag_configure("warning", foreground=ACCENT_YELLOW)
        txt.tag_configure("success", foreground=ACCENT_GREEN, font=("Consolas", 10, "bold"))
        txt.tag_configure("info", foreground=ACCENT_BLUE)
        txt.tag_configure(TITULO_ERROR, foreground=ACCENT_RED, font=("Consolas", 10, "bold"))
        txt.tag_configure(TITULO_AVISO, foreground=ACCENT_YELLOW, font=("Consolas", 10, "bold"))
        txt.tag_configure(UBICACION, foreground=ACCENT_CYAN, underline=True)
        txt.tag_configure(MARGEN, foreground=ACCENT_BLUE)
        txt.tag_configure(CODIGO, foreground=TEXT_COLOR)
        txt.tag_configure(MARCA_ERROR, foreground=ACCENT_RED, font=("Consolas", 10, "bold"))
        txt.tag_configure(MARCA_AVISO, foreground=ACCENT_YELLOW, font=("Consolas", 10, "bold"))
        txt.tag_configure(AYUDA, foreground=ACCENT_GREEN)
        txt.tag_configure(NORMAL, foreground=TEXT_COLOR, font=("Consolas", 10, "bold"))

        return {"frame": frame, "text": txt}

    def _build_status_bar(self):
        self.status_bar = tk.Frame(self, bg=BG_TOOLBAR, height=24, bd=0, padx=8, pady=2)
        self.status_bar.pack(side="bottom", fill="x")

        self.lbl_status = tk.Label(
            self.status_bar, text="Listo.", bg=BG_TOOLBAR, fg=TEXT_MUTED, font=("Segoe UI", 9)
        )
        self.lbl_status.pack(side="left")

        self.lbl_backend = tk.Label(
            self.status_bar, text="Target: NASM x86-64 Win64 ABI | GCC MinGW",
            bg=BG_TOOLBAR, fg=ACCENT_BLUE, font=("Segoe UI", 9)
        )
        self.lbl_backend.pack(side="right")

    # -----------------------------------------------------------------------
    # Lógica de Compilación y Procesamiento
    # -----------------------------------------------------------------------
    def compilar(self) -> bool:
        """Ejecuta el pipeline completo de compilación en memoria y actualiza pestañas."""
        source = self.editor.get_text().strip()
        if not source:
            messagebox.showwarning("Código Vacío", "Escribe o carga un programa TaleScript antes de compilar.")
            return False

        self.lbl_status.config(text="Compilando...", fg=ACCENT_YELLOW)
        self.update_idletasks()

        # 1. Volcado de Tokens
        self._volcar_tokens(source)

        # 2. Análisis Sintáctico y Semántico
        resultado = parsear(source)
        self._resultado = resultado

        # 3. Volcado de Tabla de Símbolos
        self._volcar_tabla_simbolos(resultado)

        # 4. Volcado de Consola / Diagnósticos (reporte detallado) + marcas en el editor
        self._volcar_consola(resultado, self.editor.get_text())
        self.editor.marcar_errores(resultado.gestor_errores.obtener_todos())

        # 5. Volcado de TAC y Tripletas
        self._volcar_tac(resultado)

        # 6. Optimizador (-O1)
        codigo_final = resultado.codigo_tac
        if self.opt_var.get() == "-O1":
            opt = Optimizador()
            codigo_opt = opt.optimizar(resultado.codigo_tac)
            self._volcar_optimizador(resultado.codigo_tac, codigo_opt)
            codigo_final = codigo_opt
        else:
            self._set_text_panel(self.tab_opt["text"], "Optimización desactivada (-O0).")

        # 7. Actualizar Grafo de la Máquina de Estados
        self.tab_graph.update_graph(resultado)

        # 8. Generación de Ensamblador NASM x86-64
        gen = GeneradorX86_64()
        asm = gen.generar(codigo_final, resultado.tabla_cadenas, resultado.tabla_simbolos)
        self._set_text_panel(self.tab_asm["text"], asm)

        if resultado.exito:
            self.lbl_status.config(text="✔ Compilación exitosa (0 errores).", fg=ACCENT_GREEN)
            return True
        else:
            primero = resultado.errores[0] if resultado.errores else None
            donde = f" Primero en la línea {primero.linea}: [{primero.codigo}] {primero.mensaje}" if primero else ""
            self.lbl_status.config(
                text=f"✖ Falló con {len(resultado.errores)} error(es).{donde}",
                fg=ACCENT_RED
            )
            # Cambiar a la pestaña de consola si hay error
            self.notebook.select(self.tab_console["frame"])
            return False

    def compilar_y_ejecutar(self):
        """Compila a binario nativo .exe y lo lanza en una ventana de consola de Windows."""
        if not self.compilar():
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(base_dir))
        runtime_c = os.path.join(root_dir, "runtime", "runtime.c")

        # Archivo temporal en la raíz o directorio de ejecución
        exe_path = os.path.join(root_dir, "juego_talescript.exe")
        asm_path = os.path.join(root_dir, "juego_talescript.asm")
        obj_path = os.path.join(root_dir, "juego_talescript.obj")

        # Guardar ensamblador
        asm_code = self.tab_asm["text"].get("1.0", "end-1c")
        with open(asm_path, "w", encoding="utf-8") as f:
            f.write(asm_code)

        # Ejecutar NASM
        try:
            subprocess.run(["nasm", "-f", "win64", asm_path, "-o", obj_path], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            messagebox.showerror(
                "NASM no encontrado",
                "No se encontró 'nasm' en el PATH de Windows.\n\n"
                "Para generar el ejecutable .exe instala NASM (winget install NASM.NASM) o revisa la Guía de Colaboradores."
            )
            return
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error en NASM", f"Error de ensamblado:\n{e.stderr}")
            return

        # Ejecutar GCC MinGW
        try:
            subprocess.run(["gcc", "-o", exe_path, obj_path, runtime_c, "-lmsvcrt"], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            messagebox.showerror(
                "GCC no encontrado",
                "No se encontró 'gcc' (MinGW-w64) en el PATH de Windows.\n\n"
                "Instala MinGW-w64 o revisa docs/guia_ejecucion_colaboradores.md."
            )
            return
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error en GCC", f"Error de enlace:\n{e.stderr}")
            return

        # Limpiar temporales
        for temp in (asm_path, obj_path):
            if os.path.exists(temp):
                try: os.remove(temp)
                except OSError: pass

        # Lanzar el ejecutable en una consola interactiva nueva de Windows
        self.lbl_status.config(text=f"✔ Ejecutable generado: {exe_path}. Lanzando consola...", fg=ACCENT_GREEN)
        subprocess.Popen(f'start cmd /k "{exe_path}"', shell=True)

    # -----------------------------------------------------------------------
    # Volcados de Información hacia las Pestañas
    # -----------------------------------------------------------------------
    def _volcar_tokens(self, source: str):
        from talescriptc.semantica.gestor_errores import GestorErrores
        ge_lex = GestorErrores()   # captura L01/L02 en vez de imprimirlos en la terminal
        lex = crear_lexer(gestor_errores=ge_lex)
        lex.input(source)
        lines = [f"{'Tipo':<16} {'Línea':<6} {'Columna':<8} Valor", "-" * 60]
        while True:
            tok = lex.token()
            if not tok:
                break
            line_start = source.rfind("\n", 0, tok.lexpos) + 1
            col = (tok.lexpos - line_start) + 1
            lines.append(f"{tok.type:<16} {tok.lineno:<6} {col:<8} {repr(tok.value)}")
        if ge_lex.lista_errores:
            lines.append("")
            lines.append("Errores léxicos (el carácter se omite y el análisis continúa):")
            for r in ge_lex.ordenados():
                lines.append(f"  [{r.codigo}] línea {r.linea}, columna {r.columna}: {r.mensaje}")
        self._set_text_panel(self.tab_tokens["text"], "\n".join(lines))

    def _volcar_tabla_simbolos(self, res: ResultadoCompilacion):
        out = res.tabla_simbolos.dump()
        self._set_text_panel(self.tab_symtab["text"], out)

    def _volcar_tac(self, res: ResultadoCompilacion):
        txt_cuads = dump_cuadruplas(res.codigo_tac)
        txt_triples = dump_tripletas(cuadruplas_a_tripletas(res.codigo_tac))
        out = f"{txt_cuads}\n\n{'='*70}\n{txt_triples}"
        self._set_text_panel(self.tab_tac["text"], out)

    def _volcar_optimizador(self, original, optimizado):
        out = [
            "=== OPTIMIZADOR (-O1) — COMPARATIVA ===",
            f"Cuádruplas originales:  {len(original)}",
            f"Cuádruplas optimizadas: {len(optimizado)}",
            f"Reducción:              {len(original) - len(optimizado)} cuádruplas eliminadas.",
            "",
            dump_cuadruplas(optimizado)
        ]
        self._set_text_panel(self.tab_opt["text"], "\n".join(out))

    def _volcar_consola(self, res: ResultadoCompilacion, fuente: str = ""):
        """Reporte detallado: línea de código, marcador ^ y sugerencia por cada diagnóstico."""
        txt = self.tab_console["text"]
        txt.config(state="normal")
        txt.delete("1.0", "end")

        if res.exito:
            txt.insert("end", "✔ Análisis léxico, sintáctico y semántico completado sin errores.\n\n", "success")
        else:
            txt.insert("end", f"✖ Se encontraron {len(res.errores)} error(es) fatales "
                              f"(clic en la ubicación para ir a la línea):\n\n", "error")

        archivo = os.path.basename(self._current_file) if self._current_file else "<editor>"
        for n, reg in enumerate(res.gestor_errores.obtener_todos()):
            tag_salto = f"ir_linea_{n}"
            for texto, estilo in segmentos_error(reg, fuente, archivo):
                tags = (estilo, tag_salto) if estilo == UBICACION else (estilo,)
                txt.insert("end", texto, tags)
            txt.insert("end", "\n")
            txt.tag_bind(tag_salto, "<Button-1>", lambda e, l=reg.linea: self.editor.ir_a_linea(l))
            txt.tag_bind(tag_salto, "<Enter>", lambda e: txt.config(cursor="hand2"))
            txt.tag_bind(tag_salto, "<Leave>", lambda e: txt.config(cursor=""))

        if res.advertencias and res.exito:
            txt.insert("end", f"{len(res.advertencias)} aviso(s).\n", "warning")

        txt.config(state="disabled")

    def _set_text_panel(self, text_widget: tk.Text, content: str):
        text_widget.config(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", content)
        text_widget.config(state="disabled")

    # -----------------------------------------------------------------------
    # Manejo de Archivos y Ejemplos
    # -----------------------------------------------------------------------
    @staticmethod
    def _carpeta_tests(carpeta: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(base_dir))
        return os.path.join(root_dir, "tests", carpeta)

    def _listar_demos_error(self) -> list:
        carpeta = self._carpeta_tests("errores_demo")
        if not os.path.isdir(carpeta):
            return []
        return sorted(f for f in os.listdir(carpeta) if f.endswith(".ts"))

    def _cargar_ejemplo(self, nombre_ejemplo: str, carpeta: str = "execution"):
        ruta = os.path.join(self._carpeta_tests(carpeta), nombre_ejemplo)

        if not os.path.exists(ruta):
            messagebox.showerror("Archivo no encontrado", f"No se encontró el ejemplo: {ruta}")
            return

        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()

        self._current_file = ruta
        self.editor.set_text(contenido)
        self.lbl_archivo.config(text=f"Archivo: {os.path.basename(ruta)}")
        self.compilar()

    def _load_default_script(self):
        self._cargar_ejemplo("historia.ts")

    def _nuevo_archivo(self):
        self._current_file = None
        self.editor.set_text('global int puntos = 0;\n\nnode inicio {\n    say "Hola, mundo TaleScript.";\n    end;\n}')
        self.lbl_archivo.config(text="Nuevo archivo")

    def _abrir_archivo(self):
        path = filedialog.askopenfilename(filetypes=[("Archivos TaleScript", "*.ts"), ("Todos los archivos", "*.*")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.editor.set_text(f.read())
            self._current_file = path
            self.lbl_archivo.config(text=f"Archivo: {os.path.basename(path)}")
            self.compilar()

    def _guardar_archivo(self):
        if not self._current_file:
            self._guardar_como()
        else:
            with open(self._current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.get_text())
            self.lbl_status.config(text=f"✔ Guardado: {self._current_file}", fg=ACCENT_GREEN)

    def _guardar_como(self):
        path = filedialog.asksaveasfilename(defaultextension=".ts", filetypes=[("Archivos TaleScript", "*.ts")])
        if path:
            self._current_file = path
            self._guardar_archivo()
            self.lbl_archivo.config(text=f"Archivo: {os.path.basename(path)}")

    def _on_code_modified(self):
        pass


def main():
    app = TaleScriptStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
