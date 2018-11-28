from schedsim.common import TaskGraph
from schedsim.generators import random_dependencies, random_levels
from schedsim.generators.elementary import bigmerge, conflux, duration_stairs, fern, fork1,\
    fork2, grid, merge_neighbours, merge_small_big, merge_triplets, plain1cpus, plain1e, plain1n, \
    size_stairs, splitters, triplets
from schedsim.generators.irw import crossv, crossvx, fastcrossv, gridcat, mapreduce, nestedcrossv
from schedsim.generators.pegasus import cybershake, epigenomics, ligo, montage, sipht
from schedsim.generators.randomized import generate_randomized_graph


def test_random_dependencies():
    graph = TaskGraph()
    random_dependencies(10, 0.2, lambda: graph.new_task(output_size=1))

    assert graph.task_count == 10
    graph.validate()


def test_random_levels():
    graph = TaskGraph()
    random_levels([3, 10, 5, 1], [0, 3, 2, 3], lambda: graph.new_task(output_size=1))

    graph.validate()
    assert graph.task_count == 19
    assert len(list(graph.arcs)) == 43


def test_elementary():
    generators = [
        (plain1n, 380),
        (plain1e, 380),
        (plain1cpus, 380),
        (triplets, 110),
        (merge_neighbours, 107),
        (merge_triplets, 111),
        (merge_small_big, 80),
        (fork1, 100),
        (fork2, 100),
        (bigmerge, 320),
        (duration_stairs, 190),
        (size_stairs, 190),
        (splitters, 7),
        (conflux, 7),
        (grid, 19),
        (fern, 10)
    ]

    for gen in generators:
        gen[0](*gen[1:]).validate()


def test_irw():
    generators = [
        (gridcat, 20),
        (crossv, 8),
        (crossvx, 4, 4),
        (fastcrossv, 8),
        (mapreduce, 160),
        (nestedcrossv, 10),
    ]

    for gen in generators:
        gen[0](*gen[1:]).validate()


def test_pegasus():
    generators = [
        (montage, 50),
        (cybershake, 50),
        (epigenomics, 50),
        (ligo, (20, 10, 15)),
        (sipht, 2)
    ]

    for gen in generators:
        gen[0](*gen[1:]).validate()


def test_randomized():
    generate_randomized_graph(10).validate()
