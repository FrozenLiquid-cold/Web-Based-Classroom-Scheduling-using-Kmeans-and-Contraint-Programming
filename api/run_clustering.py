"""Script to run K-Means clustering on database"""
import sys
from db import SessionLocal
from clustering.kmeans_cluster import cluster_all, cluster_subjects, cluster_rooms

def main():
    """Run clustering based on command line arguments"""
    db = SessionLocal()
    
    try:
        if len(sys.argv) < 2:
            print("Usage: python run_clustering.py [subjects|rooms|all] [k] [course_id]")
            print("\nExamples:")
            print("  python run_clustering.py all 3          # Cluster all (3 clusters)")
            print("  python run_clustering.py subjects 5     # Cluster subjects (5 clusters)")
            print("  python run_clustering.py rooms 3        # Cluster rooms (3 clusters)")
            print("  python run_clustering.py all 3 1        # Cluster all for course_id=1")
            sys.exit(1)
        
        command = sys.argv[1].lower()
        k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        course_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
        
        if command == "subjects":
            print(f"Clustering subjects (k={k})...")
            result = cluster_subjects(db=db, k=k, course_id=course_id)
            print(f"✓ Clustered {result['clustered_count']} subjects")
            print(f"Cluster statistics: {result.get('cluster_stats', {})}")
        
        elif command == "rooms":
            print(f"Clustering rooms (k={k})...")
            result = cluster_rooms(db=db, k=k)
            print(f"✓ Clustered {result['clustered_count']} rooms")
            print(f"Cluster statistics: {result.get('cluster_stats', {})}")
        
        elif command == "all":
            print(f"Clustering subjects and rooms (k={k})...")
            result = cluster_all(db=db, k=k, course_id=course_id, should_cluster_rooms=True)
            print(f"✓ Subjects: {result['subjects']['clustered_count']} clustered")
            print(f"✓ Rooms: {result['rooms']['clustered_count']} clustered")
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()

