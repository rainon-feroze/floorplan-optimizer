"""
Genetic algorithm loop (DEAP), per the PDF's "simplest viable version":
population of random layouts -> fitness -> select/crossover/mutate -> repeat.

This uses a single weighted-sum fitness (see fitness.py). To upgrade to true
multi-objective optimization (a Pareto front of daylight-vs-circulation-vs-
adjacency tradeoffs instead of one blended score), swap this module for
pymoo's NSGA-II -- the genome/decode/objective pieces in genome.py and
fitness.py would carry over almost unchanged, you'd just return the
itemized tuple from score_breakdown() instead of a single sum.
"""
import random
from typing import List, Tuple

from deap import base, creator, tools, algorithms

from .genome import genome_length, random_gene
from .fitness import evaluate

N_GENES = genome_length()

# Avoid re-creating DEAP classes if this module is imported twice (e.g. in a notebook)
if not hasattr(creator, "FitnessMin"):
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMin)

toolbox = base.Toolbox()
toolbox.register("attr_gene", random_gene)
toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_gene, n=N_GENES)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxBlend, alpha=0.4)
toolbox.register("mutate", tools.mutGaussian, mu=0.0, sigma=0.10, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)


def _clip(individual):
    for i, gene in enumerate(individual):
        individual[i] = min(1.0, max(0.0, gene))
    return individual


def run(
    pop_size: int = 250,
    n_generations: int = 150,
    cxpb: float = 0.6,
    mutpb: float = 0.3,
    seed: int = 42,
    verbose: bool = True,
) -> Tuple[List[float], List[float], list]:
    """Returns (best_genome_initial_gen0, best_genome_final, logbook_stats)."""
    random.seed(seed)
    pop = toolbox.population(n=pop_size)

    stats = tools.Statistics(lambda ind: ind.fitness.values[0])
    stats.register("min", min)
    stats.register("avg", lambda vals: sum(vals) / len(vals))

    logbook = tools.Logbook()
    logbook.header = ["gen", "min", "avg"]

    # gen 0 eval
    fitnesses = list(map(toolbox.evaluate, pop))
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit
    best_gen0 = list(tools.selBest(pop, 1)[0])

    record = stats.compile(pop)
    logbook.record(gen=0, **record)
    if verbose:
        print(logbook.stream)

    for gen in range(1, n_generations + 1):
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))

        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < cxpb:
                toolbox.mate(c1, c2)
                _clip(c1)
                _clip(c2)
                del c1.fitness.values
                del c2.fitness.values

        for mutant in offspring:
            if random.random() < mutpb:
                toolbox.mutate(mutant)
                _clip(mutant)
                del mutant.fitness.values

        invalid = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid)
        for ind, fit in zip(invalid, fitnesses):
            ind.fitness.values = fit

        # elitism: keep the single best individual from the previous gen
        elite = tools.selBest(pop, 1)
        offspring[0] = toolbox.clone(elite[0])

        pop[:] = offspring

        record = stats.compile(pop)
        logbook.record(gen=gen, **record)
        if verbose and (gen % 10 == 0 or gen == n_generations):
            print(logbook.stream)

    best_final = tools.selBest(pop, 1)[0]
    return best_gen0, list(best_final), logbook
