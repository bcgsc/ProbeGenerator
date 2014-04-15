"""Find the sequences of probes and print them in FASTA format.

"""
import itertools
import sys

from probe_generator import (reference,
                             coordinate_statement,
                             annotation,
                             probe_statement,
                             sequence,
                             snp_statement)

_COMPLEMENT = str.maketrans('acgtACGT', 'tgcaTGCA')


def reverse_complement(string):
    """Return the reverse-complement of a string of nucleotides.

    """
    return ''.join(reversed(string.translate(_COMPLEMENT)))


def print_fasta(head, bases):
    """Print a single string in FASTA format.

    """
    print(">{}\n{}".format(head, bases))


def combine_annotations(annotation_files):
    """Given a list of annotation files, return a single annotation.

    """
    rows = []
    for annotation_file in annotation_files:
        with open(annotation_file) as handle:
            rows.extend(annotation.parse_ucsc_file(handle))
    return rows


def probe_name(specification, coordinates, left_row, right_row):
    """Return a header for a FASTA-format probe.

    Currently the header consists of the statment's string representation, the
    coordinates of the breakpoint and the unique 'name' of each row.

    `specification` and `coordinates` are probe specification and coordinate
    dictionaries.  `left_row` and `right_row` are rows from a UCSC gene table.

    """
    return "{}_{}_{}_{}".format(
            probe_statement.to_string(specification),
            coordinate_statement.breakpoint_string(coordinates),
            left_row['name'],
            right_row['name'])


def bases_from_coordinate(coordinate, ref_genome):
    """Given a set of coordinates and a genome, return a probe sequence.

    """
    first_bases = reference.bases(
            ref_genome,
            coordinate['chromosome1'],
            coordinate['start1'],
            coordinate['end1'])
    second_bases = reference.bases(
            ref_genome,
            coordinate['chromosome2'],
            coordinate['start2'],
            coordinate['end2'])
    if coordinate['rc_side_1']:
        first_bases = reverse_complement(first_bases)
    if coordinate['rc_side_2']:
        second_bases = reverse_complement(second_bases)
    return first_bases + second_bases


def explode_statements(statements, annotation_files):
    """Yield expanded probe statements along with the associated rows.

    Yields 3-tuples of dictionaries of the form:

        (probe_specification, right_row, left_row)

    """
    for statement in statements:
        specification = probe_statement.parse(statement)
        left_rows = annotation.lookup_gene(
                specification['gene1'], annotation_files)
        right_rows = annotation.lookup_gene(
                specification['gene2'], annotation_files)
        for left, right in itertools.product(left_rows, right_rows):
            specs = probe_statement.expand(
                    specification,
                    len(annotation.exons(left)),
                    len(annotation.exons(right)))
            for spec in specs:
                yield spec, left, right


def from_coordinate(statements_file, genome_file):
    """Print a probe in FASTA format given a reference genome file and a file
    containing coordinate statements.

    """
    with open(genome_file) as genome, open(statements_file) as statements:
        ref_genome = reference.reference_genome(genome)
        for statement in statements:
            statement = statement.strip()
            coordinate = coordinate_statement.parse(statement)
            bases = bases_from_coordinate(coordinate, ref_genome)
            print_fasta(statement, bases)


def from_statements(statements_file, genome_file, annotation_files):
    """Print probes in FASTA format given a reference genome file, a file
    containing probe statements, and UCSC genome annotations.

    """
    combined_annotation = combine_annotations(annotation_files)
    with open(statements_file) as statements, open(genome_file) as genome:
        ref_genome = reference.reference_genome(genome)
        exploded_statements = explode_statements(
                statements, combined_annotation)
        for name, bases in get_sequences(exploded_statements, ref_genome):
            print_fasta(name, bases)


def from_snps(snp_file, genome_file):
    """Print probes in FASTA format given a reference genome file and a file
    containing SNP probe statements.

    """
    # TODO: there should probably be only one function like this to print all
    # kinds of probes
    with open(snp_file) as snps, open(genome_file) as genome:
        ref_genome = reference.reference_genome(genome)
        for statement in snps:
            probe = snp_statement.SnpProbe(statement.strip(), ref_genome)
            print_fasta(probe, probe.sequence())


def get_sequences(statements, genome):
    """Given 3-tuples of coordinates specifications and associated rows, yield
    the names and sequences of the probes.

    `genome` is the reference genome from which to extract the probes.

    Skips probes with redundant coordinates, printing a warning to stderr.

    """
    cached_coords = set()
    for statement in statements:
        spec, left_row, right_row = statement
        try:
            coordinate = sequence.sequence_range(spec, left_row, right_row)
            bases = bases_from_coordinate(coordinate, genome)
        except (sequence.NoFeatureError, reference.MissingChromosome) as error:
            print("{}. Skipping...".format(error), file=sys.stderr)
        coord_hash = dict_hash(coordinate)
        if not coord_hash in cached_coords:
            cached_coords.add(coord_hash)
            yield probe_name(spec, coordinate, left_row, right_row), bases
        else:
            print(
                "{} {} {} appears to be redundant. Skipping...".format(
                    probe_statement.to_string(spec),
                    left_row['name'],
                    right_row['name']),
                file=sys.stderr)


def dict_hash(dictionary):
    """Return a unique dicitonary identifier.

    Requires both the keys and values of the dictionary to be hashable.

    """
    return hash(tuple(sorted(dictionary.items())))
