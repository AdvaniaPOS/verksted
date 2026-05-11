import { api } from "./api";

/** Fetch a printable HTML view from the API (with auth) and open it in a new window
 * to leverage the browser's normal print dialog (works with any printer the OS knows
 * about, including Epson ESC/POS via vendor driver). */
export async function openPrint(path: string) {
  try {
    const r = await api.get(path, { responseType: "text" });
    const w = window.open("", "_blank", "width=420,height=720");
    if (!w) {
      alert("Pop-up blokkert. Tillat pop-up for å skrive ut.");
      return;
    }
    w.document.open();
    w.document.write(r.data as string);
    w.document.close();
  } catch (e: any) {
    alert("Utskrift feilet: " + (e?.response?.data?.detail ?? e?.message ?? e));
  }
}

/** Download raw ESC/POS bytes – for users with a print-agent that pipes to /dev/usb/lp0 etc. */
export async function downloadEscPos(path: string, filename: string) {
  const r = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
