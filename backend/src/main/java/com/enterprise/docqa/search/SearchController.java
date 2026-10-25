package com.enterprise.docqa.search;

import com.enterprise.docqa.common.BizException;
import com.enterprise.docqa.common.R;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.Map;

/** 检索透传(DESIGN §5.1 /search → Python /search) */
@RestController
@RequestMapping("/api/search")
public class SearchController {

    private final RestClient client;
    private final String baseUrl;
    private final String token;

    public SearchController(@Value("${ai.base-url}") String baseUrl,
                            @Value("${ai.internal-token}") String token) {
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(5000);
        f.setReadTimeout(30000);
        this.client = RestClient.builder().requestFactory(f).build();
        this.baseUrl = baseUrl;
        this.token = token;
    }

    @PostMapping
    public R<Object> search(@RequestBody Map<String, Object> body) {
        try {
            Object result = client.post()
                    .uri(baseUrl + "/search")
                    .header("X-Internal-Token", token)
                    .header("Content-Type", "application/json")
                    .body(body)
                    .retrieve()
                    .body(Object.class);
            return R.ok(result);
        } catch (org.springframework.web.client.RestClientResponseException e) {
            throw new BizException(5032, "AI 服务错误: " + e.getStatusCode());
        } catch (org.springframework.web.client.RestClientException e) {
            throw new BizException(5031, "AI 服务不可达");
        }
    }
}
