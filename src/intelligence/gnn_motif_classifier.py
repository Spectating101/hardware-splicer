"""
Lightweight GNN motif classifier (synthetic pretraining).

Generates small synthetic circuit graphs and trains a simple graph
neural network to detect motifs (RC filter, voltage divider, H-bridge).
Intended as a heuristic prior; not production-grade.
"""

from typing import List, Dict, Any
import torch
from torch import nn
import networkx as nx

TORCH_GEOM_AVAILABLE = False
Data = None
GCNConv = None
global_mean_pool = None
try:
    import torch_geometric  # type: ignore
    from torch_geometric.data import Data  # type: ignore
    from torch_geometric.nn import GCNConv, global_mean_pool  # type: ignore
    TORCH_GEOM_AVAILABLE = True
except ImportError:
    TORCH_GEOM_AVAILABLE = False


class SimpleGCN(nn.Module):
    def __init__(self, in_channels: int, hidden: int, out_channels: int):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden)
        self.conv2 = GCNConv(hidden, hidden)
        self.lin = nn.Linear(hidden, out_channels)

    def forward(self, x, edge_index, batch):
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = global_mean_pool(x, batch)
        return self.lin(x)


class GNNSignatureClassifier:
    """
    Synthetic GNN classifier to score circuit motifs.
    Uses synthetic graphs; acts as a lightweight prior.
    """
    MOTIFS = ["rc_filter", "voltage_divider", "h_bridge", "power_filter", "op_amp_like"]

    def __init__(self):
        self.model = None
        self.label_to_idx = {m: i for i, m in enumerate(self.MOTIFS)}
        self.idx_to_label = {i: m for m, i in self.label_to_idx.items()}
        self.device = torch.device("cpu")

    def is_available(self) -> bool:
        return TORCH_GEOM_AVAILABLE

    def _node_features(self, classes: List[str]) -> torch.Tensor:
        # Simple one-hot over known classes; unknown collapses to last bin
        vocab = ["Resistor", "Capacitor", "MOSFET", "Transformer", "Connector", "Unknown"]
        feats = []
        for cls in classes:
            vec = [0]*len(vocab)
            if cls in vocab:
                vec[vocab.index(cls)] = 1
            else:
                vec[-1] = 1
            feats.append(vec)
        return torch.tensor(feats, dtype=torch.float)

    def _edge_index_from_pairs(self, edges: List[List[int]]) -> torch.Tensor:
        if not edges:
            return torch.empty((2, 0), dtype=torch.long)
        src, dst = zip(*edges)
        return torch.tensor([src, dst], dtype=torch.long)

    def _build_synthetic_dataset(self, n_samples: int = 100) -> List[Data]:
        """
        Generate tiny synthetic graphs for motifs.
        This is intentionally simple and small; just enough to provide a prior.
        """
        data_list = []
        for motif in self.MOTIFS:
            for i in range(n_samples // len(self.MOTIFS)):
                if motif == "rc_filter":
                    classes = ["Resistor", "Capacitor"]
                    edges = [[0,1],[1,0]]
                elif motif == "voltage_divider":
                    classes = ["Resistor","Resistor"]
                    edges = [[0,1],[1,0]]
                elif motif == "h_bridge":
                    classes = ["MOSFET","MOSFET","MOSFET","MOSFET"]
                    edges = [[0,1],[1,2],[2,3],[3,0]]
                elif motif == "power_filter":
                    classes = ["Transformer","Capacitor","Capacitor"]
                    edges = [[0,1],[0,2],[1,2]]
                elif motif == "op_amp_like":
                    classes = ["Resistor","Resistor","Capacitor","Connector"]
                    edges = [[0,3],[1,3],[2,3]]
                x = self._node_features(classes)
                edge_index = self._edge_index_from_pairs(edges)
                y = torch.tensor([self.label_to_idx[motif]], dtype=torch.long)
                data_list.append(Data(x=x, edge_index=edge_index, y=y))
        return data_list

    def train_synthetic(self, epochs: int = 30, lr: float = 0.01):
        if not TORCH_GEOM_AVAILABLE:
            return False
        dataset = self._build_synthetic_dataset()
        if not dataset:
            return False
        loader = torch_geometric.loader.DataLoader(dataset, batch_size=8, shuffle=True)
        self.model = SimpleGCN(in_channels=len(dataset[0].x[0]), hidden=16, out_channels=len(self.MOTIFS)).to(self.device)
        opt = torch.optim.Adam(self.model.parameters(), lr=lr)
        loss_fn = nn.CrossEntropyLoss()
        self.model.train()
        for _ in range(epochs):
            for batch in loader:
                batch = batch.to(self.device)
                opt.zero_grad()
                out = self.model(batch.x, batch.edge_index, batch.batch)
                loss = loss_fn(out, batch.y)
                loss.backward()
                opt.step()
        return True

    def predict(self, G: nx.Graph) -> List[Dict[str, Any]]:
        """
        Score motifs on a provided graph.
        """
        if not self.model:
            trained = self.train_synthetic()
            if not trained:
                return []
        # Convert graph to pyg Data
        comps = [n for n, attr in G.nodes(data=True) if attr.get("type") == "component"]
        if not comps:
            return []
        node_classes = [G.nodes[n].get("cls", "Unknown") for n in comps]
        x = self._node_features(node_classes)
        # Map node name -> idx
        node_idx = {n: i for i, n in enumerate(comps)}
        edges = []
        for u, v in G.edges():
            if u in node_idx and v in node_idx:
                edges.append([node_idx[u], node_idx[v]])
                edges.append([node_idx[v], node_idx[u]])
        edge_index = self._edge_index_from_pairs(edges)
        data = Data(x=x, edge_index=edge_index, y=torch.tensor([0]))
        data.batch = torch.zeros(data.num_nodes, dtype=torch.long)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(data.x, data.edge_index, data.batch)
            probs = torch.softmax(logits, dim=-1).squeeze(0)
        results = []
        for i, p in enumerate(probs):
            if p.item() > 0.3:
                results.append({"structure": self.idx_to_label[i], "probability": float(p.item())})
        return results
