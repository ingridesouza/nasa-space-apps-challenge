import type { Map } from 'maplibre-gl'
import { useEffect, useState } from 'react'

import { getConditions, getLayers, getNomenclature, getRoverPhotos } from './api/client'
import type { ConditionsResponse, LayerMeta, NomenclatureFeature, RouteOption, RoverPhotoPin } from './api/types'
import { ConditionsPanel } from './components/ConditionsPanel'
import { LayerControlPanel } from './components/LayerControlPanel'
import { PhotoLightbox } from './components/PhotoLightbox'
import { PointInfoPanel } from './components/PointInfoPanel'
import { RoutePanel } from './components/RoutePanel'
import { TopHud } from './components/TopHud'
import { MapCanvas } from './map/MapCanvas'
import type { PickMode } from './map/MapCanvas'

export default function App() {
  const [map, setMap] = useState<Map | null>(null)
  const [selectedPoint, setSelectedPoint] = useState<{ lat: number; lon: number } | null>(null)
  const [layersMeta, setLayersMeta] = useState<LayerMeta[] | null>(null)
  const [layersError, setLayersError] = useState<string | null>(null)
  const [conditions, setConditions] = useState<ConditionsResponse | null>(null)
  const [conditionsError, setConditionsError] = useState<string | null>(null)
  const [nomenclature, setNomenclature] = useState<NomenclatureFeature[]>([])

  const [routeMode, setRouteMode] = useState(false)
  const [routeOrigin, setRouteOrigin] = useState<{ lat: number; lon: number } | null>(null)
  const [routeDestination, setRouteDestination] = useState<{ lat: number; lon: number } | null>(null)
  const [activeRoute, setActiveRoute] = useState<RouteOption | null>(null)

  const [photos, setPhotos] = useState<RoverPhotoPin[]>([])
  const [photosVisible, setPhotosVisible] = useState(true)
  const [openPhotoIndex, setOpenPhotoIndex] = useState<number | null>(null)
  const [zoom, setZoom] = useState<number | null>(null)
  // trilha do Curiosity (feature 08) -- entra desligada, igual
  // Relevo/THEMIS, até o usuário ligar pelo LayerControlPanel.
  const [roverTrackVisible, setRoverTrackVisible] = useState(false)

  function handlePhotoPinClick(photo: RoverPhotoPin) {
    const idx = photos.findIndex((p) => p.url === photo.url)
    if (idx >= 0) setOpenPhotoIndex(idx)
  }

  useEffect(() => {
    getLayers()
      .then(setLayersMeta)
      .catch((e) => setLayersError(String(e)))

    getConditions()
      .then(setConditions)
      .catch((e) => setConditionsError(String(e)))

    // lista pequena (13 feições), falha silenciosa não impede o resto do app
    getNomenclature()
      .then(setNomenclature)
      .catch(() => {})

    // "rastro do rover" -- pins nas posições reais das ~200 fotos
    getRoverPhotos()
      .then(setPhotos)
      .catch(() => {})
  }, [])

  function handleMapClick(lat: number, lon: number) {
    if (!routeMode) {
      setSelectedPoint({ lat, lon })
      return
    }
    if (!routeOrigin) {
      setRouteOrigin({ lat, lon })
    } else if (!routeDestination) {
      setRouteDestination({ lat, lon })
    } else {
      // terceiro clique dentro do modo rota: recomeça a escolha a partir daqui
      setRouteOrigin({ lat, lon })
      setRouteDestination(null)
    }
  }

  function resetRoutePoints() {
    setRouteOrigin(null)
    setRouteDestination(null)
    setActiveRoute(null)
  }

  function toggleRouteMode() {
    setRouteMode((on) => {
      const next = !on
      if (next) {
        setSelectedPoint(null)
      } else {
        setRouteOrigin(null)
        setRouteDestination(null)
        setActiveRoute(null)
      }
      return next
    })
  }

  const pickMode: PickMode = !routeMode ? 'point' : !routeOrigin ? 'pick-origin' : !routeDestination ? 'pick-destination' : 'pick-origin'

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {layersMeta && (
        <MapCanvas
          layersMeta={layersMeta}
          pickMode={pickMode}
          onMapReady={setMap}
          onMapClick={handleMapClick}
          routeOrigin={routeOrigin ? [routeOrigin.lat, routeOrigin.lon] : null}
          routeDestination={routeDestination ? [routeDestination.lat, routeDestination.lon] : null}
          activeRoute={activeRoute}
          photos={photos}
          photosVisible={photosVisible}
          onPhotoClick={handlePhotoPinClick}
          onZoomChange={setZoom}
          roverTrackVisible={roverTrackVisible}
        />
      )}

      {/* Grade visual só de apresentação -- CTX/HiRISE em Gale só
       * existem em preto-e-branco no catálogo do Mars Trek (confirmado,
       * sem produto colorido pra essa região), então tingimos a imagem
       * real com `mix-blend-mode: color` (preserva toda a luminância/
       * textura real, só substitui o matiz) pra lembrar a cor real da
       * poeira marciana -- mesma técnica usada em visualizações
       * públicas da própria NASA. Nenhum dado científico passa por
       * aqui (slope/elevação/amostragem continuam no pixel original). */}
      {layersMeta && <div className="h2g2-mars-tint" />}

      {!layersMeta && !layersError && (
        <div className="h2g2-mono h2g2-dim" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          carregando camadas da API...
        </div>
      )}

      {layersError && (
        <div
          className="h2g2-mono"
          style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--h2g2-danger)' }}
        >
          Não consegui falar com a API ({layersError}). Ela está rodando?
        </div>
      )}

      <div className="h2g2-vignette" />
      <div className="h2g2-corner h2g2-corner--tl" />
      <div className="h2g2-corner h2g2-corner--tr" />
      <div className="h2g2-corner h2g2-corner--bl" />
      <div className="h2g2-corner h2g2-corner--br" />
      <TopHud lastClick={selectedPoint} sol={conditions?.sol ?? null} zoom={zoom} />

      {/* Coluna esquerda: camadas + condições num flex-column só, com
       * limite de altura real -- antes eram dois painéis ancorados
       * independentemente (um do topo, outro do bottom) na mesma
       * coluna, e se o de cima crescesse mais que o espaço disponível,
       * o de baixo (pintado depois) cobria o resto dele sem aviso
       * nenhum (bug real reportado pelo usuário). */}
      <div
        style={{
          position: 'absolute',
          top: 88,
          bottom: 'var(--s-4)',
          left: 'var(--s-4)',
          width: 240,
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--s-3)',
        }}
      >
        <LayerControlPanel
          map={map}
          photosVisible={photosVisible}
          onTogglePhotos={() => setPhotosVisible((v) => !v)}
          photoCount={photos.length}
          roverTrackVisible={roverTrackVisible}
          onToggleRoverTrack={() => setRoverTrackVisible((v) => !v)}
        />
        <ConditionsPanel conditions={conditions} error={conditionsError} />
      </div>

      <button
        onClick={toggleRouteMode}
        className="h2g2-panel h2g2-mono"
        style={{
          position: 'absolute',
          top: 'var(--s-4)',
          left: '50%',
          transform: 'translateX(-50%)',
          padding: 'var(--s-2) var(--s-4)',
          fontSize: 'var(--t-small)',
          cursor: 'pointer',
          color: routeMode ? 'var(--hud-cyan)' : 'var(--ink)',
          border: routeMode ? '1px solid var(--hud-cyan)' : undefined,
        }}
      >
        {routeMode ? '✕ cancelar rota' : '◇ planejar rota'}
      </button>

      {/* instrução grande e colorida -- cor bate com o marcador que vai
       * aparecer no mapa (verde=origem, vermelho=destino), pra deixar
       * óbvio o que vai acontecer no próximo clique. Some assim que os
       * dois pontos já foram marcados. */}
      {routeMode && !(routeOrigin && routeDestination) && (
        <div
          className="h2g2-panel h2g2-mono"
          style={{
            position: 'absolute',
            top: 64,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: 'var(--s-3) var(--s-5)',
            fontSize: 'var(--t-body)',
            fontWeight: 600,
            textAlign: 'center',
            whiteSpace: 'nowrap',
            color: !routeOrigin ? 'var(--verdict-seguro)' : 'var(--mars2)',
            border: `1px solid ${!routeOrigin ? 'var(--verdict-seguro)' : 'var(--mars2)'}`,
            pointerEvents: 'none',
          }}
        >
          {!routeOrigin ? 'PASSO 1/2 · clique no mapa para marcar a ORIGEM' : 'PASSO 2/2 · clique no mapa para marcar o DESTINO'}
        </div>
      )}

      {!routeMode && (
        <PointInfoPanel point={selectedPoint} onClose={() => setSelectedPoint(null)} nomenclature={nomenclature} />
      )}
      {routeMode && (
        <RoutePanel
          origin={routeOrigin}
          destination={routeDestination}
          onClose={toggleRouteMode}
          onReset={resetRoutePoints}
          onActiveRouteChange={setActiveRoute}
        />
      )}

      {openPhotoIndex !== null && (
        <PhotoLightbox
          photos={photos.map((p) => ({ url: p.url, sol: p.sol, camera: p.camera, caption: `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}` }))}
          index={openPhotoIndex}
          onClose={() => setOpenPhotoIndex(null)}
          onIndexChange={setOpenPhotoIndex}
        />
      )}
    </div>
  )
}
