export default function Kasse() {
  return (
    <div className="max-w-2xl mx-auto mt-12 text-center space-y-4">
      <div className="text-6xl">🛍</div>
      <h1 className="text-3xl font-bold text-slate-800">Butikk-kasse kommer snart</h1>
      <p className="text-slate-600">
        POS-modulen for direktesalg over disk er under utvikling. Den vil fungere
        sammen med Susoft-integrasjonen og bruke samme kunde- og lagerregister
        som verkstedet.
      </p>
      <div className="card text-left text-sm space-y-2">
        <h2 className="font-semibold text-slate-700">Planlagt funksjonalitet:</h2>
        <ul className="list-disc list-inside text-slate-600 space-y-1">
          <li>Strekkode/SKU-skanning</li>
          <li>Vipps / kort / kontant betaling</li>
          <li>Kvitteringsutskrift via samme printer-config</li>
          <li>Automatisk lager-uttrekk i Susoft</li>
          <li>Dagsoppgjør og rapporter</li>
        </ul>
      </div>
    </div>
  );
}
