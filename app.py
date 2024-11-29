import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sqlite3
import pandas as pd
import qrcode
from fpdf import FPDF
from PIL import Image, ImageTk
from datetime import datetime
import os
import tempfile
import threading
import urllib.parse
import logging
import gc  
from typing import List, Tuple

PRIMARY_COLOR = "#003366"
TEXT_COLOR = "#FFFFFF"
QR_IMAGE_SIZE = 150
DATABASE = "qr_codes.db" 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseManager:
    @staticmethod
    def initialize_database():
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS qr_codes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        contenido TEXT NOT NULL,
                        fecha_creacion TEXT NOT NULL,
                        descripcion TEXT,
                        personalizacion TEXT
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Database initialization error: {e}")
            raise

    @staticmethod
    def create_qr_code(contenido: str, descripcion: str, personalizacion: str = "") -> bool:
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO qr_codes (contenido, fecha_creacion, descripcion, personalizacion)
                    VALUES (?, ?, ?, ?)
                ''', (contenido, fecha_creacion, descripcion, personalizacion))
                conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error creating QR in DB: {e}")
            return False

    @staticmethod
    def get_all_qr_codes() -> List[Tuple]:
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM qr_codes')
                return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error fetching QRs: {e}")
            return []

    @staticmethod
    def delete_all_qr_codes() -> bool:
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM qr_codes')
                conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error deleting QRs: {e}")
            return False

class QRGenerator:
    @staticmethod
    def create_qr_content(code: str, description: str, personalization: str = "") -> str:
        qr_content = (
            f"PROCHAP\nCódigo: {code}\nDescripción: {description}\n"
            f"Personalización: {personalization}"
        )
        whatsapp_message = urllib.parse.quote(qr_content)
        whatsapp_url = f"https://wa.me/?text={whatsapp_message}"
        return qr_content + f"\nCompartir por WhatsApp: {whatsapp_url}"

    @staticmethod
    def generate_qr_image(text: str, size: int = QR_IMAGE_SIZE) -> Image.Image:
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2
            )
            qr.add_data(text)
            qr.make(fit=True)
            qr_image = qr.make_image(fill="black", back_color="white").convert('RGB')
            return qr_image.resize((size, size), Image.LANCZOS)
        except Exception as e:
            logging.error(f"Error generating QR image: {e}")
            return None

class QRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PROCHAP - Generador de Códigos QR")
        self.root.geometry("800x600")
        self.root.configure(bg=PRIMARY_COLOR)
        self.qr_images = []
        DatabaseManager.initialize_database()
        self.create_widgets()

    def create_widgets(self):
        style = ttk.Style(self.root)
        style.configure('TButton', font=('Segoe UI', 10), padding=6)

        
        frame_manual = tk.LabelFrame(self.root, text="Generar QR Manual", bg=PRIMARY_COLOR, fg=TEXT_COLOR)
        frame_manual.pack(padx=10, pady=10, fill="x")

        tk.Label(frame_manual, text="Código:", bg=PRIMARY_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Label(frame_manual, text="Descripción:", bg=PRIMARY_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Label(frame_manual, text="Personalización:", bg=PRIMARY_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, padx=5, pady=5, sticky="e")

        self.code_entry = ttk.Entry(frame_manual, width=30)
        self.description_entry = ttk.Entry(frame_manual, width=30)
        self.personalization_entry = ttk.Entry(frame_manual, width=30)

        self.code_entry.grid(row=0, column=1, padx=5, pady=5)
        self.description_entry.grid(row=1, column=1, padx=5, pady=5)
        self.personalization_entry.grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(frame_manual, text="Generar y Guardar QR", command=self.generate_and_save_qr).grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(frame_manual, text="Importar desde Excel", command=self.import_from_excel).grid(row=4, column=0, columnspan=2, pady=10)

        
        frame_controls = tk.LabelFrame(self.root, text="Controles", bg=PRIMARY_COLOR, fg=TEXT_COLOR)
        frame_controls.pack(padx=10, pady=10, fill="x")

        
        ttk.Button(frame_controls, text="Exportar a PDF", command=self.export_pdf_async).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame_controls, text="Borrar Todo", command=self.clear_all_qrs).grid(row=0, column=2, padx=5, pady=5)

        
        self.display_frame = tk.Frame(self.root, bg=PRIMARY_COLOR)
        self.display_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.canvas = tk.Canvas(self.display_frame, bg=PRIMARY_COLOR)
        self.scrollbar = ttk.Scrollbar(self.display_frame, orient="vertical", command=self.canvas.yview)
        self.qr_display = ttk.Frame(self.canvas)

        self.qr_display.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.qr_display, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        
        self.progress_frame = tk.Frame(self.root, bg=PRIMARY_COLOR)
        self.progress_frame.pack(padx=10, pady=10, fill="x")
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(fill="x")
        self.progress_label = tk.Label(self.progress_frame, text="", bg=PRIMARY_COLOR, fg=TEXT_COLOR)
        self.progress_label.pack()

        
        self.progress_frame.pack_forget()

    def show_progress(self, show: bool = True):
        if show:
            self.progress_frame.pack(padx=10, pady=10, fill="x")
        else:
            self.progress_frame.pack_forget()

    def update_progress(self, value: int, max_value: int):
        percentage = int((value / max_value) * 100)
        self.progress_bar["value"] = percentage
        self.progress_label.config(text=f"Progreso: {percentage}%")
        self.root.update_idletasks()

    def generate_and_save_qr(self):
        code = self.code_entry.get().strip()
        description = self.description_entry.get().strip()
        personalization = self.personalization_entry.get().strip()

        if not code or not description:
            messagebox.showerror("Error", "Por favor ingrese un código y una descripción.")
            return

        try:
            qr_content = QRGenerator.create_qr_content(code, description, personalization)
            if DatabaseManager.create_qr_code(qr_content, description, personalization):
                qr_image = QRGenerator.generate_qr_image(qr_content)
                if qr_image:
                    self.show_qr_image(qr_image, f"{code} - {description}")
                    messagebox.showinfo("Éxito", "QR generado y guardado correctamente.")
                    self.clear_entries()
                else:
                    messagebox.showerror("Error", "No se pudo generar la imagen QR.")
            else:
                messagebox.showerror("Error", "No se pudo guardar el QR en la base de datos.")
        except Exception as e:
            logging.error(f"Error generating QR: {e}")
            messagebox.showerror("Error", f"Error al generar QR: {str(e)}")

    def clear_entries(self):
        self.code_entry.delete(0, tk.END)
        self.description_entry.delete(0, tk.END)
        self.personalization_entry.delete(0, tk.END)

    def import_from_excel(self):
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("Excel files", "*.xlsx;*.xls"), ("All files", "*.*")]
            )
            if not file_path:
                return

            df = pd.read_excel(file_path, keep_default_na=False)
            df = df.dropna(how='all')

            # Ventana para seleccionar columnas
            seleccion_columnas = tk.Toplevel(self.root)
            seleccion_columnas.title("Seleccionar Columnas")

            columnas = df.columns.tolist()

            tk.Label(seleccion_columnas, text="Selecciona la columna 'Código':").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.codigo_combobox = ttk.Combobox(seleccion_columnas, values=columnas)
            self.codigo_combobox.grid(row=0, column=1, padx=5, pady=5)
            self.codigo_combobox.current(0)

            tk.Label(seleccion_columnas, text="Selecciona la columna 'Descripción':").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.descripcion_combobox = ttk.Combobox(seleccion_columnas, values=columnas)
            self.descripcion_combobox.grid(row=1, column=1, padx=5, pady=5)
            self.descripcion_combobox.current(0)

            ttk.Button(seleccion_columnas, text="Aceptar", command=lambda: self.procesar_excel(file_path, seleccion_columnas)).grid(row=2, column=0, columnspan=2, pady=10)

        except FileNotFoundError:
            messagebox.showerror("Error", "Archivo Excel no encontrado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al abrir el archivo Excel: {str(e)}")

    def procesar_excel(self, file_path, seleccion_columnas):
        codigo_col = self.codigo_combobox.get()
        descripcion_col = self.descripcion_combobox.get()

        if not codigo_col or not descripcion_col:
            messagebox.showerror("Error", "Debes seleccionar las columnas 'Código' y 'Descripción'.")
            return

        seleccion_columnas.destroy()
        self.importar_datos(file_path, codigo_col, descripcion_col)

    def importar_datos(self, file_path, codigo_col, descripcion_col):
        try:
            df = pd.read_excel(file_path, keep_default_na=False)
            df = df.dropna(how='all')

            personalizacion_col = next((col for col in df.columns if 'personalizacion' in col.lower().replace(' ', '')), None)
            if personalizacion_col is None:
                df['personalizacion'] = ''
                personalizacion_col = 'personalizacion'

            total_rows = len(df)
            self.show_progress(True)

            success_count = 0
            error_count = 0
            skipped_count = 0

            for index, row in df.iterrows():
                try:
                    code = str(row[codigo_col]).strip()
                    description = str(row[descripcion_col]).strip()
                    personalization = str(row.get(personalizacion_col, '')).strip()

                    if not code or not description:
                        logging.warning(f"Fila {index + 2}: código o descripción vacíos, saltando.")
                        skipped_count += 1
                        continue

                    qr_content = QRGenerator.create_qr_content(code, description, personalization)
                    if DatabaseManager.create_qr_code(qr_content, description, personalization):
                        qr_image = QRGenerator.generate_qr_image(qr_content)
                        if qr_image:
                            self.show_qr_image(qr_image, f"{code} - {description}")
                            success_count += 1
                            qr_image.close()  
                            gc.collect()  
                        else:
                            logging.error(f"Fila {index + 2}: no se pudo generar la imagen QR.")
                            error_count += 1
                    else:
                        logging.error(f"Fila {index + 2}: no se pudo guardar en la base de datos.")
                        error_count += 1

                except KeyError as e:
                    logging.error(f"Fila {index + 2}: columna faltante - {e}")
                    error_count += 1
                except Exception as e:
                    logging.error(f"Fila {index + 2}: error inesperado - {e}")
                    error_count += 1

                self.update_progress(index + 1, total_rows)

            self.show_progress(False)

            message = (
                f"Proceso completado.\n"
                f"QRs generados exitosamente: {success_count}\n"
                f"Filas saltadas (vacías o sin código/descripción): {skipped_count}"
            )
            if error_count > 0:
                message += f"\nErrores encontrados: {error_count}"
            messagebox.showinfo("Resultado de importación", message)

        except Exception as e:
            self.show_progress(False)
            logging.error(f"Error general al procesar el archivo Excel: {e}")
            messagebox.showerror("Error", f"Error al procesar el archivo Excel: {str(e)}")

    def export_pdf_async(self):
        threading.Thread(target=self.export_pdf, daemon=True).start()

    def export_pdf(self):
        try:
            qr_data = DatabaseManager.get_all_qr_codes()
            if not qr_data:
                self.root.after(0, lambda: messagebox.showwarning("Advertencia", "No hay códigos QR para exportar a PDF."))
                return

            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], title="Guardar PDF")
            if not file_path:
                return

            self.root.after(0, self.show_progress, True)

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            total_qrs = len(qr_data)

            for i, (_, contenido, fecha_creacion, descripcion, personalizacion) in enumerate(qr_data):
                if i > 0 and i % 3 == 0:
                    pdf.add_page()

                qr_image = QRGenerator.generate_qr_image(contenido, size=100)
                if not qr_image:
                    logging.error(f"No se pudo generar la imagen QR para el contenido del registro {i + 1}.")
                    continue

                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                    temp_file_path = temp_file.name
                    qr_image.save(temp_file_path, format="PNG")

                try:
                    current_y = 10 + (i % 3) * 90
                    pdf.image(temp_file_path, x=10, y=current_y, w=40, h=40)
                    pdf.set_xy(60, current_y)
                    pdf.multi_cell(0, 10, txt=f"Descripción: {descripcion}\nFecha: {fecha_creacion}\nPersonalización: {personalizacion}")
                except Exception as e:
                    logging.error(f"Error al incluir la imagen QR en el PDF: {e}")
                finally:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)

                qr_image.close()
                gc.collect()  
                self.root.after(0, self.update_progress, i + 1, total_qrs)

            pdf.output(file_path)
            self.root.after(0, self.show_progress, False)
            self.root.after(0, lambda: messagebox.showinfo("Exportación completada", f"PDF guardado como {file_path}"))

        except Exception as e:
            logging.error(f"Error exporting to PDF: {e}")
            self.root.after(0, self.show_progress, False)
            self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo exportar a PDF: {str(e)}"))

    def show_all_qr_codes_async(self):
        threading.Thread(target=self.show_all_qr_codes, daemon=True).start()

    def show_all_qr_codes(self):
        try:
            for widget in self.qr_display.winfo_children():
                widget.destroy()
            self.qr_images.clear()

            records = DatabaseManager.get_all_qr_codes()
            total_records = len(records)
            self.root.after(0, self.show_progress, True)

            for i, record in enumerate(records):
                qr_id, contenido, fecha_creacion, descripcion, personalizacion = record
                qr_image = QRGenerator.generate_qr_image(contenido)
                if qr_image:
                    self.root.after(0, self.show_qr_image, qr_image, f"ID: {qr_id} - {descripcion}\nFecha: {fecha_creacion}")
                    qr_image.close()
                    gc.collect()
                self.root.after(0, self.update_progress, i + 1, total_records)

            self.root.after(0, self.show_progress, False)
        except Exception as e:
            logging.error(f"Error displaying QRs: {e}")
            self.root.after(0, self.show_progress, False)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error al mostrar QRs: {str(e)}"))

    def show_qr_image(self, qr_image, description):
        try:
            tk_image = ImageTk.PhotoImage(qr_image)
        
            self.qr_images.append(tk_image)
  
            frame = ttk.Frame(self.qr_display, relief="solid", padding=10)
            frame.pack(padx=5, pady=5, fill="x", expand=True)

            label_image = tk.Label(frame, image=tk_image)
            label_image.image = tk_image  
            label_image.pack(side="left", padx=10, pady=10)
  
            label_desc = ttk.Label(frame, text=description, wraplength=200)
            label_desc.pack(side="left", padx=10, pady=10)
  
            save_button = ttk.Button(frame, text="Guardar QR", command=lambda img=qr_image: self.  save_individual_qr(img))
            save_button.pack(side="right", padx=10, pady=10)

        except Exception as e:
            logging.error(f"Error displaying QR image: {e}")
            messagebox.showerror("Error", f"Error al mostrar la imagen QR: {str(e)}")


    def save_individual_qr(self, qr_image):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")], title="Guardar QR como")
            if file_path:
                qr_image.save(file_path, "PNG")
                messagebox.showinfo("Éxito", "Imagen QR guardada correctamente")
        except Exception as e:
            logging.error(f"Error saving individual QR: {e}")
            messagebox.showerror("Error", f"Error al guardar la imagen: {str(e)}")

    def clear_all_qrs(self):
        if messagebox.askyesno("Confirmar", "¿Está seguro de que desea borrar todos los códigos QR?"):
            if DatabaseManager.delete_all_qr_codes():
                for widget in self.qr_display.winfo_children():
                    widget.destroy()
                self.qr_images.clear()
                messagebox.showinfo("Borrado", "Todos los códigos QR han sido borrados.")
            else:
                messagebox.showerror("Error", "No se pudieron borrar los códigos QR.")

def main():
    try:
        root = tk.Tk()
        app = QRApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Main application error: {e}")
        messagebox.showerror("Error", f"Error en la aplicación principal: {str(e)}")

if __name__ == "__main__":
    main()

