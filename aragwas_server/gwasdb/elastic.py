from elasticsearch import Elasticsearch, helpers
from elasticsearch_dsl import Search, Q

from aragwas.settings import ES_HOST
from .parsers import parse_snpeff
import logging
import json
import os
import numpy as np
import re
import operator

GENE_ID_PATTERN = re.compile('^[a-z]{2}([\\d]{1})G\\w+$', re.IGNORECASE)

# Get an instance of a logger
logger = logging.getLogger(__name__)

es = Elasticsearch([ES_HOST],timeout=60)

BULK_INDEX_COUNT = 1000
ES_TEMPLATE_PATH = os.path.join(os.path.join(os.path.dirname(__file__),'es_templates'))

def check_server():
    """Check if server is running"""
    return es.ping()

def check_genotype_data():
    """Checks if the genotype data is fully indexed"""
    GENE_COUNT_TO_CHECK = 33341
    SNP_COUNT_TO_CHECK = 10700998
    gene_count = es.count('genotype',doc_type='genes')['count']
    snps_count = es.count('genotype',doc_type='snps')['count']
    if gene_count != GENE_COUNT_TO_CHECK:
        raise Exception('Only %s instead of %s genes found' % (gene_count,GENE_COUNT_TO_CHECK))
    if snps_count != SNP_COUNT_TO_CHECK:
        raise Exception('Only %s instead of %s SNPs found' % (snps_count,SNP_COUNT_TO_CHECK))


def check_indices():
    """Initializes the ES indices"""

    # check if index exists
    indices_exists = es.indices.exists(
        'aragwas') or es.indices.exists('geno_*', allow_no_indices=False)
    if indices_exists:
       raise Exception('Indices already exist. Delete before you continue')

    # create the indices
    with open(os.path.join(ES_TEMPLATE_PATH, 'es_aragwas.json'), 'r') as fh:
        aragwas_settings = json.load(fh)

    with open(os.path.join(ES_TEMPLATE_PATH,'es_genotype.json'), 'r') as fh:
        genotype_settings = json.load(fh)

    # put index template
    es.indices.put_template('aragwas', aragwas_settings)
    # put index template
    es.indices.put_template('geno_*', genotype_settings)

def load_snps_by_region(chrom, start, end):
    """Retrieve snp information by region"""
    index = 'geno_%s'
    if len(chrom) > 3:
        index = index % chrom
    else:
        index = index % 'chr' + chrom
    search_snps = Search().using(es).doc_type('snps').index(index).filter("range", position={"lte": end, "gte":start})
    return {snp.position: snp.to_dict() for snp in search_snps.scan() }

def load_snps(chrom, positions):
    """Retrieve snp information"""
    index = 'geno_%s'
    if len(chrom) > 3:
        index = index % chrom
    else:
        index = index % 'chr' + chrom
    if isinstance(positions, np.ndarray):
        pos = positions.tolist()
    else:
        pos = positions
    resp = es.mget(body={'ids':pos}, index=index, doc_type='snps')
    return [{doc['_id']: doc['_source']} if doc['found'] else {} for doc in resp['docs']]


def autocomplete_genes(term):
    """For autocomplete searches"""
    resp = es.search(index='genotype',doc_type='genes',_source=["suggest", "positions","strand","chr","type"],
        body={"suggest": {
                "gene-suggest": {
                    "prefix":term,
                    "completion": {
                        "field": "suggest"
                    }
                }
        }})
    return [{'id':option['_id'], 'name': option['text'],'strand': option['_source']['strand'], 'chr': option['_source']['chr'], 'type': option['_source']['type'], 'positions':option['_source']['positions']} for option in resp['suggest']['gene-suggest'][0]['options']]


def load_gene_by_id(id):
    """Retrive genes by id"""
    matches = GENE_ID_PATTERN.match(id)
    if not matches:
        raise Exception('Wrong Gene ID %s' % id)
    chrom = matches.group(1)
    doc = es.get('geno_chr%s' % chrom, id, doc_type='genes', _source=['name','chr','positions','type','strand', 'isoforms'], realtime=False)
    if not doc['found']:
        raise Exception('Gene with ID %s not found' %id)
    gene = doc['_source']
    gene['id'] = doc['_id']
    return gene

def load_gene_associations(id):
    """Retrive associations by neighboring gene id"""
    matches = GENE_ID_PATTERN.match(id)
    if not matches:
        raise Exception('Wrong Gene ID %s' % id)
    chrom = matches.group(1)
    asso_search = Search(using=es).doc_type('associations').source(exclude=['isoforms','GO'])
    q = Q({'nested':{'path':'snps.annotations', 'query':{'match':{'snps.annotations.gene_name':id}}}})
    asso_search = asso_search.query(q).sort('-pvalue')
    results = asso_search[0:min(500, asso_search.count())].execute()
    associations = results.to_dict()['hits']['hits']
    return [{association['_id']: association['_source']} if association['found'] else {} for association in associations]

def load_gene_snps(id):
    """Retrive associations by neighboring gene id"""
    snp_search = Search(using=es).doc_type('snps')
    q = Q({'nested':{'path':'annotations', 'query':{'match':{'annotations.gene_name':id}}}})
    snp_search = snp_search.query(q).sort('position')
    results = snp_search[0:min(500, snp_search.count())].execute()
    associations = results.to_dict()['hits']['hits']
    return [{association['_id']: association['_source']} for association in associations]

def get_top_genes():
    """Retrive associations by neighboring gene id"""
    # get list of genes, scan result so ES doesn;t rank & sort ===> TOO SLOW
    # Instead, look at top 500 associations and their genes (priorly filtering for small pvalue)
    s = Search(using=es, doc_type='associations')
    results = s.query('range', pvalue={'lte': 1e-7}).sort('-pvalue').source(['snps'])[0:500].execute().to_dict()['hits']['hits']
    gene_scores = {}
    for snp in results:
        if 'gene_name' in snp['annotations'].keys():
            id = snp['annotations']['gene_name']
            if id in gene_scores.keys():
                gene_scores[id] += 1
            else:
                gene_scores[id] = 1
    gene_scores = sorted(gene_scores.items, key=operator.itemgetter(1))[::-1]
    return gene_scores[:min(8, len(gene_scores))]


def load_top_associations():
    """Retrieve top asssociations"""

def index_associations(study, associations):
    """indexes associations"""



def index_genes(genes):
    """Indexes the genes"""
    num_genes = len(genes)
    documents = [{'_index':'geno_%s' % gene['chr'].lower(),'_type':'genes','_id':gene_id,'_source':gene} for gene_id, gene in genes.items()]
    success, errors = helpers.bulk(es,documents,chunk_size=10000,stats_only=True)
    return success, errors


def index_snps(snpeff_file):
    """indexes the snps"""
    success, errors = helpers.bulk(es,_get_snps_document(snpeff_file), stats_only=True, chunk_size=10000)
    return success, errors

def _get_association_document(study, top_associations):
    for assoc in top_associations:
        source = assoc.copy()
        source['study'] = study
        yield {
            '_index':'aragwas','_type':'associations','_id': '%s_%s_%s' % (study.pk, assoc['chr'], assoc['position']),'_source':source
        }

def _get_snps_document(snpeff_file):
    with open(snpeff_file,'r') as content:
        is_custom_snp_eff = True
        for row in content:
            if row[0] == '#':
                is_custom_snp_eff = False
                continue
            fields = row.split("\t")
            snp = parse_snpeff(fields, is_custom_snp_eff)
            action = {'_index':'geno_%s' % snp['chr'].lower(),'_type':'snps','_id':snp['position'],'_source':snp}
            yield action