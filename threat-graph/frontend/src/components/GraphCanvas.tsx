import cytoscape from "cytoscape";
import { useEffect, useMemo, useRef } from "react";
import type { GraphSnapshot, Provenance } from "../types";

interface GraphCanvasProps {
  snapshot: GraphSnapshot;
  visibleProvenance: Provenance[];
  selectedKey?: string | null;
  onSelect?: (key: string | null) => void;
}

export function GraphCanvas({ snapshot, visibleProvenance, selectedKey, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const instanceRef = useRef<cytoscape.Core | null>(null);

  const elements = useMemoElements(snapshot, visibleProvenance);

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: {
        name: "cose",
        animate: false,
        padding: 40,
        idealEdgeLength: 120,
        nodeRepulsion: 6500,
        gravity: 0.4,
      },
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.25,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-family": "Inter, Segoe UI, sans-serif",
            "font-size": 10,
            color: "#dbeafe",
            "text-valign": "center",
            "text-halign": "center",
            "text-wrap": "wrap",
            "text-max-width": "110px",
            width: 44,
            height: 44,
            "background-color": "#334155",
            "border-width": 2,
            "border-color": "#64748b",
            "text-outline-width": 2,
            "text-outline-color": "#0b1220",
            "transition-property": "background-color, border-color",
            "transition-duration": 180,
          },
        },
        {
          selector: 'node[type = "indicator"]',
          style: { "background-color": "#d97706", "border-color": "#fbbf24" },
        },
        {
          selector: 'node[type = "event"]',
          style: { "background-color": "#1d4ed8", "border-color": "#60a5fa" },
        },
        {
          selector: 'node[type = "domain"]',
          style: { "background-color": "#0f766e", "border-color": "#5eead4" },
        },
        {
          selector: "node.selected",
          style: { "border-width": 5, "border-color": "#f8fafc", "background-color": "#7c3aed" },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(confidence, 0, 1, 1.5, 5)",
            "line-color": "#22c55e",
            "target-arrow-color": "#22c55e",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(relationship)",
            "font-family": "Inter, Segoe UI, sans-serif",
            "font-size": 8,
            color: "#94a3b8",
            "text-background-color": "#0b1220",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            opacity: 0.85,
          },
        },
        {
          selector: 'edge[provenance = "inferred"]',
          style: {
            "line-color": "#a855f7",
            "target-arrow-color": "#a855f7",
            "line-style": "dashed",
            "line-dash-pattern": [6, 4],
          },
        },
      ],
    });

    instanceRef.current = cy;
    cy.on("tap", "node", (event) => onSelect?.(event.target.id()));
    cy.on("tap", (event) => {
      if (event.target === cy) onSelect?.(null);
    });

    const observer = new ResizeObserver(() => cy.resize());
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      cy.destroy();
      instanceRef.current = null;
    };
  }, [elements, onSelect]);

  useEffect(() => {
    const cy = instanceRef.current;
    if (!cy) return;
    cy.nodes().removeClass("selected");
    if (selectedKey && cy.getElementById(selectedKey).nonempty()) {
      cy.getElementById(selectedKey).addClass("selected");
    }
  }, [selectedKey, elements]);

  return <div className="graph-canvas" ref={containerRef} />;
}

function useMemoElements(snapshot: GraphSnapshot, visibleProvenance: Provenance[]) {
  return useMemo(() => {
    const nodes = snapshot.nodes.map((node) => ({
      data: {
        id: node.key,
        label: node.label || node.key,
        type: node.type,
        degree: node.degree,
        risk: node.risk_score ?? 0,
      },
    }));
    const edges = snapshot.edges
      .filter((edge) => visibleProvenance.includes(edge.provenance))
      .map((edge) => ({
        data: {
          id: edge.key || `${edge.source}-${edge.target}-${edge.relationship}`,
          source: edge.source,
          target: edge.target,
          relationship: edge.relationship,
          provenance: edge.provenance,
          confidence: edge.confidence,
        },
      }));
    return [...nodes, ...edges];
  }, [snapshot, visibleProvenance]);
}
