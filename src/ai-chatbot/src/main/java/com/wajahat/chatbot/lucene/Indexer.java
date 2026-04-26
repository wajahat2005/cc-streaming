package com.wajahat.chatbot.lucene;

/**
 * 🏗️ Indexer: Responsible for building the Lucene Knowledge Base at startup.
 */
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.document.StringField;
import org.apache.lucene.document.TextField;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.store.ByteBuffersDirectory;
import org.apache.lucene.store.Directory;

import java.io.IOException;
import java.util.List;

public class Indexer {

    public static Directory createIndex(String kbFilePath) throws IOException {
        Directory directory = new ByteBuffersDirectory();
        StandardAnalyzer analyzer = new StandardAnalyzer();
        IndexWriterConfig config = new IndexWriterConfig(analyzer);
        IndexWriter writer = new IndexWriter(directory, config);

        List<DataStore.FAQEntry> dataset = DataStore.getData(kbFilePath);

        for (DataStore.FAQEntry entry : dataset) {
            Document doc = new Document();
            
            // TextField: Tokenized and indexed
            doc.add(new TextField("question", entry.question.toLowerCase(), Field.Store.YES));
            doc.add(new TextField("answer", entry.answer, Field.Store.YES));
            
            // StringField: Indexed but NOT tokenized (Perfect for matching specific intent tags)
            doc.add(new StringField("intent", entry.intent.toLowerCase(), Field.Store.YES));

            writer.addDocument(doc);
        }

        writer.close();
        return directory;
    }
}
