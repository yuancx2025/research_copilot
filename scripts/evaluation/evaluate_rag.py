"""
RAG Evaluation Script

Demonstrates how to evaluate RAG system performance using the evaluation framework.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from rag.evaluator import RAGEvaluator
from rag.retriever import Retriever
from rag.reranker import Reranker
from langchain_core.documents import Document
from unittest.mock import MagicMock
import config


def create_sample_documents():
    """Create sample documents for evaluation"""
    return [
        Document(
            page_content="Machine learning is a subset of artificial intelligence that focuses on algorithms.",
            metadata={"parent_id": "doc1", "source": "ml_intro.pdf", "source_type": "local"}
        ),
        Document(
            page_content="Deep learning uses neural networks with multiple layers to learn complex patterns.",
            metadata={"parent_id": "doc2", "source": "deep_learning.pdf", "source_type": "local"}
        ),
        Document(
            page_content="Python is a popular programming language for data science and machine learning.",
            metadata={"parent_id": "doc3", "source": "python_guide.pdf", "source_type": "local"}
        ),
        Document(
            page_content="Natural language processing enables computers to understand human language.",
            metadata={"parent_id": "doc4", "source": "nlp_basics.pdf", "source_type": "local"}
        ),
        Document(
            page_content="Web development involves creating websites and web applications.",
            metadata={"parent_id": "doc5", "source": "web_dev.pdf", "source_type": "local"}
        ),
    ]


def create_evaluation_dataset():
    """Create evaluation dataset with queries and relevant documents"""
    return [
        {
            "query": "What is machine learning?",
            "relevant_doc_ids": ["doc1", "doc2"],  # doc1 and doc2 are relevant
            "description": "Query about machine learning basics"
        },
        {
            "query": "How does deep learning work?",
            "relevant_doc_ids": ["doc2"],  # Only doc2 is relevant
            "description": "Query specifically about deep learning"
        },
        {
            "query": "Python programming for data science",
            "relevant_doc_ids": ["doc3"],  # Only doc3 is relevant
            "description": "Query about Python and data science"
        },
        {
            "query": "Natural language processing",
            "relevant_doc_ids": ["doc4"],  # Only doc4 is relevant
            "description": "Query about NLP"
        },
    ]


def simulate_retrieval(query: str, documents: list, k: int = 5, use_reranking: bool = False):
    """
    Simulate retrieval process.
    
    In a real scenario, this would use the actual Retriever with a vector store.
    For demonstration, we simulate retrieval based on keyword matching.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Score documents based on keyword overlap
    scored_docs = []
    for doc in documents:
        doc_words = set(doc.page_content.lower().split())
        overlap = len(query_words & doc_words)
        score = overlap / len(query_words) if query_words else 0
        scored_docs.append((doc, score))
    
    # Sort by score (descending)
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    # Return top k
    if use_reranking:
        # Simulate reranking: use cross-encoder-like scoring
        reranked = []
        for doc, score in scored_docs[:k*2]:  # Retrieve more for reranking
            # Simulate improved scoring (in reality, cross-encoder would do this)
            improved_score = score * 1.2 if score > 0.3 else score * 0.8
            reranked.append((doc, improved_score))
        reranked.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in reranked[:k]]
    else:
        return [doc for doc, _ in scored_docs[:k]]


def evaluate_retrieval_method(evaluator, documents, dataset, use_reranking: bool = False):
    """Evaluate a retrieval method on the dataset"""
    results = []
    
    for item in dataset:
        query = item["query"]
        relevant_ids = item["relevant_doc_ids"]
        
        # Simulate retrieval
        retrieved_docs = simulate_retrieval(query, documents, k=5, use_reranking=use_reranking)
        
        # Evaluate
        metrics = evaluator.evaluate_retrieval(query, retrieved_docs, relevant_ids, k=5)
        
        results.append({
            "query": query,
            "description": item["description"],
            "metrics": metrics,
            "retrieved_count": len(retrieved_docs),
            "relevant_count": len(relevant_ids)
        })
    
    return results


def print_evaluation_results(results, method_name: str):
    """Print evaluation results in a formatted way"""
    print(f"\n{'='*60}")
    print(f"Evaluation Results: {method_name}")
    print(f"{'='*60}\n")
    
    # Aggregate metrics
    total_hit_rate = 0
    total_mrr = 0
    total_precision = 0
    total_recall = 0
    
    for i, result in enumerate(results, 1):
        metrics = result["metrics"]
        print(f"Query {i}: {result['query']}")
        print(f"  Description: {result['description']}")
        print(f"  Hit Rate @ 5: {metrics['hit_rate@k']:.3f}")
        print(f"  MRR: {metrics['mrr']:.3f}")
        print(f"  Precision @ 5: {metrics['precision@k']:.3f}")
        print(f"  Recall @ 5: {metrics['recall@k']:.3f}")
        print(f"  Retrieved: {result['retrieved_count']} docs")
        print(f"  Relevant: {result['relevant_count']} docs")
        print()
        
        total_hit_rate += metrics['hit_rate@k']
        total_mrr += metrics['mrr']
        total_precision += metrics['precision@k']
        total_recall += metrics['recall@k']
    
    # Average metrics
    n = len(results)
    print(f"{'─'*60}")
    print(f"Average Metrics:")
    print(f"  Hit Rate @ 5: {total_hit_rate/n:.3f}")
    print(f"  MRR: {total_mrr/n:.3f}")
    print(f"  Precision @ 5: {total_precision/n:.3f}")
    print(f"  Recall @ 5: {total_recall/n:.3f}")
    print(f"{'='*60}\n")
    
    return {
        "hit_rate@k": total_hit_rate/n,
        "mrr": total_mrr/n,
        "precision@k": total_precision/n,
        "recall@k": total_recall/n
    }


def compare_methods(evaluator, documents, dataset):
    """Compare baseline vs reranked retrieval"""
    print("\n" + "="*60)
    print("RAG System Evaluation: Baseline vs Reranked Retrieval")
    print("="*60)
    
    # Evaluate baseline
    baseline_results = evaluate_retrieval_method(
        evaluator, documents, dataset, use_reranking=False
    )
    baseline_avg = print_evaluation_results(baseline_results, "Baseline (No Reranking)")
    
    # Evaluate with reranking
    reranked_results = evaluate_retrieval_method(
        evaluator, documents, dataset, use_reranking=True
    )
    reranked_avg = print_evaluation_results(reranked_results, "With Reranking")
    
    # Compare
    print("\n" + "="*60)
    print("Comparison: Baseline vs Reranked")
    print("="*60)
    print(f"\nHit Rate @ 5:")
    print(f"  Baseline: {baseline_avg['hit_rate@k']:.3f}")
    print(f"  Reranked: {reranked_avg['hit_rate@k']:.3f}")
    print(f"  Improvement: {(reranked_avg['hit_rate@k'] - baseline_avg['hit_rate@k']):.3f} ({(reranked_avg['hit_rate@k'] / baseline_avg['hit_rate@k'] - 1) * 100:.1f}%)")
    
    print(f"\nMRR:")
    print(f"  Baseline: {baseline_avg['mrr']:.3f}")
    print(f"  Reranked: {reranked_avg['mrr']:.3f}")
    print(f"  Improvement: {(reranked_avg['mrr'] - baseline_avg['mrr']):.3f} ({(reranked_avg['mrr'] / baseline_avg['mrr'] - 1) * 100:.1f}%)")
    
    print(f"\nPrecision @ 5:")
    print(f"  Baseline: {baseline_avg['precision@k']:.3f}")
    print(f"  Reranked: {reranked_avg['precision@k']:.3f}")
    print(f"  Improvement: {(reranked_avg['precision@k'] - baseline_avg['precision@k']):.3f} ({(reranked_avg['precision@k'] / baseline_avg['precision@k'] - 1) * 100:.1f}%)")
    
    print(f"\nRecall @ 5:")
    print(f"  Baseline: {reranked_avg['recall@k']:.3f}")
    print(f"  Reranked: {reranked_avg['recall@k']:.3f}")
    print(f"  Improvement: {(reranked_avg['recall@k'] - baseline_avg['recall@k']):.3f} ({(reranked_avg['recall@k'] / baseline_avg['recall@k'] - 1) * 100:.1f}%)")
    print("="*60 + "\n")


def main():
    """Main evaluation function"""
    print("Initializing RAG Evaluation Framework...")
    
    # Create evaluator
    evaluator = RAGEvaluator()
    
    # Create sample documents
    print("Creating sample documents...")
    documents = create_sample_documents()
    
    # Create evaluation dataset
    print("Creating evaluation dataset...")
    dataset = create_evaluation_dataset()
    
    print(f"Dataset: {len(dataset)} queries, {len(documents)} documents\n")
    
    # Run evaluation
    compare_methods(evaluator, documents, dataset)
    
    # Demonstrate individual metric usage
    print("\n" + "="*60)
    print("Individual Metric Examples")
    print("="*60)
    
    query = "What is machine learning?"
    retrieved = simulate_retrieval(query, documents, k=3)
    relevant_ids = ["doc1", "doc2"]
    
    print(f"\nQuery: {query}")
    print(f"Retrieved documents: {[d.metadata['parent_id'] for d in retrieved]}")
    print(f"Relevant documents: {relevant_ids}")
    
    hit_rate = evaluator.hit_rate_at_k(retrieved, relevant_ids, k=3)
    mrr = evaluator.mrr(retrieved, relevant_ids)
    precision = evaluator.precision_at_k(retrieved, relevant_ids, k=3)
    recall = evaluator.recall_at_k(retrieved, relevant_ids, k=3)
    
    print(f"\nMetrics:")
    print(f"  Hit Rate @ 3: {hit_rate:.3f}")
    print(f"  MRR: {mrr:.3f}")
    print(f"  Precision @ 3: {precision:.3f}")
    print(f"  Recall @ 3: {recall:.3f}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

