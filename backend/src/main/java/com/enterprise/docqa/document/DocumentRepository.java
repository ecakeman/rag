package com.enterprise.docqa.document;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.List;

public interface DocumentRepository extends JpaRepository<DocumentEntity, Long> {

    Page<DocumentEntity> findByStatus(DocStatus status, Pageable pageable);

    Page<DocumentEntity> findByTitleContainingIgnoreCase(String q, Pageable pageable);

    Page<DocumentEntity> findByStatusAndTitleContainingIgnoreCase(DocStatus status, String q, Pageable pageable);

    List<DocumentEntity> findByStatusAndUpdatedAtBefore(DocStatus status, OffsetDateTime threshold);

    @Query("select d from DocumentEntity d where d.status in :statuses order by d.updatedAt desc")
    List<DocumentEntity> findTopByStatuses(@Param("statuses") List<DocStatus> statuses, Pageable pageable);
}
