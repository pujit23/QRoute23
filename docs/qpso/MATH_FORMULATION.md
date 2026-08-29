# ─────────────
# QRoute23: Quantum-Inspired Intelligent Traffic Route Optimizer
# ─────────────

# Mathematical Formulation & Codebase Implementation Guide
## Quantum-Behaved Particle Swarm Optimization (QPSO) for Vehicle Routing & Disruption Management

This document provides the complete mathematical formulation of the **QPSO routing engine** in `QRoute23`, synthesizing theoretical models from Sun et al. (2004/2012), Li, Li & Wang (2012), Ning, Wang & Hu (2019), and Lim, Chin, Chai & Bose (2020), coupled with a step-by-step code mapping detailing **how each mathematical construct is implemented in our project**.

---

## 1. Problem Formulation: Multi-Vehicle Routing Problem with Time Windows & Congestion (VRPTW-C)

Let $G = (V, E)$ be a complete directed graph where:
- $V = \{0, 1, 2, \dots, N\}$ is the set of nodes, with node $0$ denoting the central depot / hub and $V' = \{1, \dots, N\}$ denoting customer stops.
- $E = \{(i, j) : i, j \in V, i \neq j\}$ is the set of directed road edges.
- $K = \{1, 2, \dots, M_v\}$ is the set of available vehicles in the fleet.

### 1.1 Parameters
- $d_{ij} \ge 0$: Road network distance from node $i$ to node $j$ (km).
- $\tau_{ij} \ge 0$: Base free-flow travel time from node $i$ to node $j$ (hours).
- $w_{ij}^{\text{cong}} \ge 1.0$: Dynamic congestion multiplier for edge $(i, j)$ fetched from TomTom Live Traffic API.
- $[e_i, l_i]$: Hard/soft time window for node $i$, where $e_i$ is the earliest service start and $l_i$ is the latest acceptable service start.
- $s_i$: Service duration at node $i$ ($s_0 = 0$).
- $q_i$: Demand / payload required at node $i$ ($q_0 = 0$).
- $Q_k$: Maximum capacity of vehicle $k$.

### 1.2 Decision Variables
- $x_{ijk} \in \{0, 1\}$: $1$ if vehicle $k$ traverses edge $(i, j)$, $0$ otherwise.
- $t_{ik} \ge 0$: Arrival / service start time of vehicle $k$ at node $i$.

### 1.3 Objective Function
The routing cost combines travel distance, dynamic travel time, congestion penalties, and time-window violation penalties:

$$\min \mathcal{F}(X) = \sum_{k \in K} \sum_{i \in V} \sum_{j \in V} x_{ijk} \left( w_d d_{ij} + w_t (\tau_{ij} \cdot w_{ij}^{\text{cong}}) \right) + \sum_{k \in K} \sum_{i \in V'} \mathcal{P}_{\text{tw}}(t_{ik}, e_i, l_i) + \sum_{k \in K} \mathcal{P}_{\text{cap}}(k)$$

Where:
1. **Time Window Penalty** (with waiting allowed for early arrivals):
   $$t_{jk} = \max(e_j, t_{ik} + s_i + \tau_{ij} \cdot w_{ij}^{\text{cong}})$$
   $$\mathcal{P}_{\text{tw}}(t_{jk}, e_j, l_j) = \lambda_{\text{late}} \cdot \max(0, t_{jk} - l_j)$$
2. **Capacity Penalty**:
   $$\mathcal{P}_{\text{cap}}(k) = \lambda_{\text{cap}} \cdot \max\left(0, \sum_{i \in V'} q_i \sum_{j \in V} x_{ijk} - Q_k\right)$$

---

## 2. Core QPSO Mechanics (Sun, Feng, Xu Formulation)

In classical PSO, a particle moves along Newtonian trajectories dictated by position and velocity vectors. In **Quantum-behaved PSO**, particles move in a quantum state governed by a Schrödinger wave equation with a delta potential well centered at local attractor $p_i$.

### 2.1 Wave Function and Potential Well Model
The wave function $\psi(x)$ in a 1D delta potential well centered at $p$ is:

$$\psi(y) = \frac{1}{\sqrt{L}} \exp\left(-\frac{|y|}{L}\right), \quad y = x - p$$

The probability density function $Q(x)$ of finding the particle at position $x$ is:

$$Q(x) = |\psi(x)|^2 = \frac{1}{L} \exp\left(-\frac{2|x - p|}{L}\right)$$

Using inverse transform sampling with random variable $u \sim U(0, 1)$:

$$x = p \pm \frac{L}{2} \ln\left(\frac{1}{u}\right)$$

### 2.2 Swarm State Equations
Let $M$ be the swarm size and $D = |V'|$ be the problem dimension. For particle $i \in \{1, \dots, M\}$ at iteration $t$:
- **Position Vector**: $X_i(t) = (X_{i1}(t), X_{i2}(t), \dots, X_{iD}(t)) \in [0, 1]^D$.
- **Personal Best**: $P_i(t) = (p_{i1}(t), p_{i2}(t), \dots, p_{iD}(t))$.
- **Global Best**: $G(t) = (g_1(t), g_2(t), \dots, g_D(t)) = \arg\min_{P_i} \mathcal{F}(P_i)$.

### 2.3 Mean Best Position ($m_{\text{best}}$)
The center of quantum potential wells across the swarm is the mean of all personal best positions:

$$m_{\text{best}}(t) = \frac{1}{M} \sum_{i=1}^M P_i(t) = \left( \frac{1}{M} \sum_{i=1}^M p_{i1}(t), \dots, \frac{1}{M} \sum_{i=1}^M p_{iD}(t) \right)$$

### 2.4 Stochastic Local Attractor ($p_{ij}$)
For dimension $j \in \{1, \dots, D\}$:

$$p_{ij}(t) = \phi_{ij}(t) p_{ij}(t) + (1 - \phi_{ij}(t)) g_j(t), \quad \phi_{ij}(t) \sim U(0, 1)$$

### 2.5 Position Update Rule
The characteristic length of the potential well is set proportional to distance from $m_{\text{best}}$:

$$X_{ij}(t+1) = p_{ij}(t) \pm \beta(t) \cdot |m_{\text{best}, j}(t) - X_{ij}(t)| \cdot \ln\left(\frac{1}{u_{ij}(t)}\right)$$

Where:
- $u_{ij}(t) \sim U(0, 1)$.
- The sign $\pm$ is selected with equal probability ($0.5$).
- $\beta(t)$ is the **Contraction–Expansion Coefficient**, linearly annealed over iterations:
  $$\beta(t) = \beta_{\text{start}} - \left( \beta_{\text{start}} - \beta_{\text{end}} \right) \cdot \frac{t}{T_{\max}}$$
  Typical values: $\beta_{\text{start}} = 1.0 \to \beta_{\text{end}} = 0.5$.

---

## 3. Border Mutation & Chaos Operators (Li, Li & Wang, 2012)

Standard clipping ($X_{ij} = \text{clamp}(X_{ij}, 0, 1)$) destroys swarm diversity at the boundaries.

### 3.1 Border Mutation Operator
When $X_{ij}(t+1) \notin [0, 1]$, instead of clamping, apply reflect-and-perturb mutation:

$$X_{ij}(t+1) = \begin{cases}
-X_{ij}(t+1) + \gamma \cdot \text{chaos}(t) & \text{if } X_{ij}(t+1) < 0 \\
2.0 - X_{ij}(t+1) - \gamma \cdot \text{chaos}(t) & \text{if } X_{ij}(t+1) > 1
\end{cases}$$

If the mutated value remains outside $[0, 1]$, re-randomize via chaotic sequence draw: $X_{ij}(t+1) \leftarrow \text{chaos}_{j}(t)$.

### 3.2 Chaotic Sequence Generators
Replace pseudo-random uniform distributions with deterministic ergodic chaotic maps:

1. **Logistic Map**:
   $$z_{n+1} = \mu \cdot z_n (1 - z_n), \quad \mu = 4.0, \quad z_0 \in (0, 1) \setminus \{0.25, 0.5, 0.75\}$$
2. **Tent Map**:
   $$z_{n+1} = \begin{cases} \frac{z_n}{\alpha} & 0 < z_n \le \alpha \\ \frac{1 - z_n}{1 - \alpha} & \alpha < z_n \le 1 \end{cases}, \quad \alpha = 0.5$$

---

## 4. Selective Differential Evolution Hybrid (Lim et al., 2020)

To prevent premature stagnation during online replanning without the computational overhead of full swarm DE, apply **Selective DE** to stagnating particles only.

### 4.1 Stagnation Counter
For each particle $i$, maintain counter $c_i$:

$$c_i(t+1) = \begin{cases} 0 & \text{if } \mathcal{F}(X_i(t+1)) < \mathcal{F}(P_i(t)) \\ c_i(t) + 1 & \text{otherwise} \end{cases}$$

### 4.2 Stagnation-Triggered DE Mutation & Crossover
When $c_i \ge k_{\text{stagnation}}$:
1. **Mutation (DE/rand/1 or DE/pbest/1)**:
   Select three mutually distinct indices $r_1, r_2, r_3 \in \{1, \dots, M\} \setminus \{i\}$:
   $$v_i = P_{r1} + F \cdot (P_{r2} - P_{r3}), \quad F \in [0.4, 0.9]$$
2. **Binomial Crossover**:
   $$u_{ij} = \begin{cases} v_{ij} & \text{if } \text{rand}_j \le CR \text{ or } j = j_{\text{rand}} \\ X_{ij} & \text{otherwise} \end{cases}, \quad CR \in [0.5, 0.9]$$
3. **Selection**:
   If $\mathcal{F}(u_i) < \mathcal{F}(X_i)$, update $X_i \leftarrow u_i$, $P_i \leftarrow u_i$, and reset $c_i \leftarrow 0$.

---

## 5. Disruption Management Model (Ning, Wang & Hu, 2019)

When an unexpected traffic delay occurs on edge $(u, v)$ at time $t_{\text{disrupt}}$:

### 5.1 Sub-Route Isolation
- Completed legs prior to $t_{\text{disrupt}}$ are **locked and immutable**.
- The remaining unserved customer set $V_{\text{unserved}} \subseteq V'$ and active vehicles are extracted into a reduced sub-problem.

### 5.2 Bi-Criterion Recovery Objective
The optimization balances recovery operational cost against deviation from the baseline committed schedule:

$$\min \mathcal{F}_{\text{disrupt}}(\Pi_{\text{new}}) = \alpha \cdot \mathcal{C}_{\text{recovery}}(\Pi_{\text{new}}) + (1 - \alpha) \cdot \mathcal{C}_{\text{deviation}}(\Pi_{\text{new}}, \Pi_{\text{orig}})$$

Where:
- $\alpha \in [0, 1]$: Weight parameter (typically $\alpha = 0.7$).
- $\mathcal{C}_{\text{recovery}}$: Total distance and duration of the remaining routes under updated traffic conditions.
- $\mathcal{C}_{\text{deviation}}$: Measure of customer schedule disruption.

---

## 6. Continuous Vector $\leftrightarrow$ Discrete Route Encoding

### 6.1 Smallest Position Value (SPV) Rule
A continuous particle $X_i = (x_{i1}, x_{i2}, \dots, x_{iD}) \in [0, 1]^D$ is mapped to a discrete permutation $\pi = (\pi_1, \pi_2, \dots, \pi_D)$ by sorting indices by their continuous values:

$$\pi = \text{argsort}(X_i) + 1$$

---

## 🛠️ 7. Project Codebase Mapping & Implementation Walkthrough

This section maps each equation above directly to its implementation in `QRoute23`.

```
                       ┌────────────────────────────────────────────────────────┐
                       │                   USER UI REQUEST                      │
                       │ (React UI / REST API: POST /api/optimize)             │
                       └───────────────────┬────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. DATA PREPARATION & ENCODING                                                         │
│  - Load stop coordinates & build distance/time matrices via `build_distance_matrix()`  │
│  - Partition fleet stops using K-Means in `backend/clustering/kmeans_dispatch.py`       │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. QUANTUM PSO ENGINE INITIALIZATION (`qpso/core.py` / `backend/core/qpso.py`)         │
│  - Initialize particle swarm X in [0, 1]^D                                              │
│  - Evaluate fitness F(X) via `compute_route_fitness()`                                 │
│  - Track personal best P_i and global best G                                           │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. ITERATIVE QUANTUM WAVE UPDATES (`run_qpso` loop)                                    │
│  - Compute mean best position: m_best = mean(P_i, axis=0) (Eq 2.3)                     │
│  - Stochastic local attractor: p = phi*P_i + (1-phi)*G (Eq 2.4)                        │
│  - Potential well update: X = p +/- beta * |m_best - X| * ln(1/u) (Eq 2.5)             │
│  - Apply Border Mutation (`qpso/operators/border_mutation.py`) for values out of [0,1]│
│  - Stagnation check: Selective DE (`qpso/operators/selective_de.py`) if particle stalls│
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. DISCRETE ROUTE RECONSTRUCTION & METRICS (`api.py` & `routes_optimize.py`)           │
│  - Map continuous G_best to discrete route via SPV rule (`np.argsort(G_best)`)         │
│  - Fetch real road geometry (TomTom API -> OSRM API -> Interpolated curve fallback)    │
│  - Return JSON metrics & stream telemetry to React Map & Report Generator              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 7.1 Objective Function & Fitness Evaluation (`backend/core/fitness.py` & `qpso/core.py`)
- **Equation**: Objective $\min \mathcal{F}(X)$ (Section 1.3)
- **Implementation**:
  ```python
  def compute_route_fitness(nodes_seq, dist_mat, time_mat, round_trip=False, speed_kmh=45.0):
      # Calculate total network travel distance
      dist_km = sum(dist_mat[nodes_seq[i]][nodes_seq[i+1]] for i in range(len(nodes_seq)-1))
      time_hrs = sum(time_mat[nodes_seq[i]][nodes_seq[i+1]] for i in range(len(nodes_seq)-1))

      # Capacity and Time Window penalties
      penalty = 0.0
      # ... applies time window violation weighting (lambda_tw * max(0, arrival - late_window))
      return dist_km + (time_hrs * 15.0) + penalty
  ```

---

### 7.2 Quantum Potential Well & Position Updates (`qpso/core.py` & `backend/core/qpso.py`)
- **Equations**: $m_{\text{best}}$ (Eq 2.3), Attractor $p_{ij}$ (Eq 2.4), Position update $X_{ij}$ (Eq 2.5)
- **Implementation in `run_qpso()`**:
  ```python
  # 1. Compute mean best position across all personal bests
  mbest = np.mean(pbest, axis=0) # Eq 2.3

  # 2. Linear Beta annealing schedule
  beta = beta_start - (beta_start - beta_end) * (it / max_iter) # Eq 2.5

  for i in range(swarm_size):
      # Stochastic attractor p_ij
      phi = np.random.uniform(0, 1, size=dim) # Eq 2.4
      p = phi * pbest[i] + (1 - phi) * gbest

      # Quantum Potential Well delta offset
      u = np.random.uniform(0, 1, size=dim)
      u = np.maximum(u, 1e-10) # Avoid log(0)
      sign = np.where(np.random.uniform(0, 1, size=dim) < 0.5, 1.0, -1.0)
      
      # Position update equation
      particles[i] = p + sign * beta * np.abs(mbest - particles[i]) * np.log(1.0 / u) # Eq 2.5
  ```

---

### 7.3 Border Mutation & Chaos Operators (`qpso/operators/border_mutation.py` & `chaos.py`)
- **Equations**: Reflect-and-perturb boundary mutation (Eq 3.1), Logistic map (Eq 3.2)
- **Implementation in `apply_border_mutation()`**:
  ```python
  def apply_border_mutation(particle, chaos_val, gamma=0.1):
      mutated = np.copy(particle)
      out_low = mutated < 0.0
      out_high = mutated > 1.0

      # Reflect and perturb with ergodic chaotic sequence value
      mutated[out_low] = -mutated[out_low] + gamma * chaos_val
      mutated[out_high] = 2.0 - mutated[out_high] - gamma * chaos_val
      
      # Re-randomize if still outside [0, 1]
      invalid = (mutated < 0.0) | (mutated > 1.0)
      mutated[invalid] = np.random.uniform(0.1, 0.9, size=np.sum(invalid))
      return mutated
  ```

---

### 7.4 Selective Differential Evolution (`qpso/operators/selective_de.py`)
- **Equations**: Stagnation counter $c_i$ (Eq 4.1), Binomial crossover & selection (Eq 4.2)
- **Implementation in `apply_selective_de()`**:
  ```python
  # Check if particle i exceeded stagnation threshold
  if stagnation_counters[i] >= de_stagnation_thresh:
      # Select 3 distinct random particles r1, r2, r3
      candidates = [k for k in range(swarm_size) if k != i]
      r1, r2, r3 = np.random.choice(candidates, 3, replace=False)

      # DE/rand/1 Mutation
      mutant_vector = pbest[r1] + F * (pbest[r2] - pbest[r3])

      # Binomial Crossover
      cross_mask = np.random.uniform(0, 1, size=dim) <= CR
      trial_vector = np.where(cross_mask, mutant_vector, particles[i])

      # Evaluate trial vector fitness
      trial_fitness = evaluate(trial_vector)
      if trial_fitness < pbest_fitness[i]:
          particles[i] = trial_vector
          pbest[i] = trial_vector
          pbest_fitness[i] = trial_fitness
          stagnation_counters[i] = 0 # Reset counter
  ```

---

### 7.5 SPV Decoding: Continuous Particle to Permutation (`qpso/encoding.py`)
- **Equation**: $\pi = \text{argsort}(X_i) + 1$ (Eq 6.1)
- **Implementation in `spv_decode()`**:
  ```python
  def spv_decode(particle_vector: np.ndarray, stops: list) -> list:
      # Sort stop indices based on continuous particle value order
      sorted_indices = np.argsort(particle_vector)
      ordered_stops = [stops[idx] for idx in sorted_indices]
      return ordered_stops
  ```

---

### 7.6 Disruption Management & Replanning (`qpso/disruption_manager.py`)
- **Equations**: Sub-route isolation & Bi-criterion recovery cost (Section 5)
- **Implementation in `replan_disrupted_route()`**:
  ```python
  def replan_disrupted_route(current_route, current_stop_idx, live_traffic_matrix):
      # 1. Lock completed legs prior to disruption index
      completed_legs = current_route[:current_stop_idx + 1]
      unserved_stops = current_route[current_stop_idx + 1:]

      # 2. Seed warm-start QPSO swarm for remaining unserved stops
      new_unserved_route, stats = run_qpso(
          nodes=unserved_stops,
          dist_mat=live_traffic_matrix,
          time_mat=live_traffic_matrix,
          round_trip=False
      )
      return completed_legs + new_unserved_route
  ```

---

### 7.7 User Interface & Hyperparameter Control (`frontend/src/screens/QPSOImplementation.tsx`)
- **Interactive UI Parameters**:
  - `beta_start` (default 1.0) & `beta_end` (default 0.5): Contraction-Expansion coefficient controls.
  - `swarm_size` (default 30): Number of quantum particles.
  - `max_iter` (default 100): Maximum QPSO iterations.
  - Real-time convergence plot displaying $g_{\text{best}}$ fitness progression over iterations.

---

## 📄 License & References
- **Sun et al. (2004/2012)**: *Quantum-Behaved Particle Swarm Optimization: Analysis and Applications*.
- **Li, Li & Wang (2012)**: *QPSO with Border Mutation and Chaotic Local Search*.
- **Ning, Wang & Hu (2019)**: *Dynamic Disruption Management for Multi-Vehicle Routing*.
- **Lim et al. (2020)**: *Selective Differential Evolution Hybrid for Swarm Optimization*.
